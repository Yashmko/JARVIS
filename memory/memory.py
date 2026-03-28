"""
JARVIS v2 — memory/memory.py (Phase A upgrade)

Optimized 3-tier memory:
- WAL mode SQLite (faster reads, no locks)
- Connection reuse (no reconnect per query)
- Project profiles (coding/bounty/personal/automation/client)
- Compressed old episodes
- Efficient recall with relevance scoring
"""
import json
import sqlite3
import logging
import os
from collections import deque
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    role     TEXT NOT NULL,
    task     TEXT NOT NULL,
    skill    TEXT,
    outcome  TEXT,
    duration INTEGER,
    profile  TEXT DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS summaries (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    summary TEXT NOT NULL,
    profile TEXT DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS stats (
    skill   TEXT PRIMARY KEY,
    uses    INTEGER DEFAULT 0,
    success INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pins (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    content TEXT NOT NULL,
    active  INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_episodes_task ON episodes(task);
CREATE INDEX IF NOT EXISTS idx_episodes_skill ON episodes(skill);
CREATE INDEX IF NOT EXISTS idx_episodes_profile ON episodes(profile);
CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(ts);
"""


class Memory:
    def __init__(self, window: int = 20, db_path: Path = None,
                 profile: str = "default"):
        self.window = window
        self.profile = profile
        self._short = deque(maxlen=window)

        self._db_path = db_path or Path("memory/history.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Optimized SQLite connection
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            timeout=10,
        )
        # WAL mode — faster concurrent reads, no blocking
        self._conn.execute("PRAGMA journal_mode=WAL")
        # Keep more in memory
        self._conn.execute("PRAGMA cache_size=-4000")  # 4MB cache
        # Faster writes (slightly less safe, but we have WAL)
        self._conn.execute("PRAGMA synchronous=NORMAL")
        # Store temp tables in memory
        self._conn.execute("PRAGMA temp_store=MEMORY")

        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ═════════════════════════════════════════════
    # PROFILE MANAGEMENT
    # ═════════════════════════════════════════════

    def set_profile(self, profile: str):
        """Switch memory profile: coding/bounty/personal/automation/client"""
        self.profile = profile

    def get_profile(self) -> str:
        return self.profile

    def list_profiles(self) -> list:
        """List all profiles that have episodes."""
        rows = self._conn.execute(
            "SELECT DISTINCT profile FROM episodes ORDER BY profile"
        ).fetchall()
        return [r[0] for r in rows]

    # ═════════════════════════════════════════════
    # CONTEXT PINNING
    # ═════════════════════════════════════════════

    def pin(self, content: str):
        """Pin context that persists across all queries."""
        self._conn.execute(
            "INSERT INTO pins(ts, content, active) VALUES(?,?,1)",
            (datetime.now().isoformat(), content)
        )
        self._conn.commit()

    def unpin(self, pin_id: int = None):
        """Deactivate a pin or all pins."""
        if pin_id:
            self._conn.execute("UPDATE pins SET active=0 WHERE id=?", (pin_id,))
        else:
            self._conn.execute("UPDATE pins SET active=0")
        self._conn.commit()

    def get_pins(self) -> list:
        """Get all active pins."""
        rows = self._conn.execute(
            "SELECT id, content FROM pins WHERE active=1 ORDER BY id"
        ).fetchall()
        return rows

    def get_pins_text(self) -> str:
        """Get pins formatted for system prompt."""
        pins = self.get_pins()
        if not pins:
            return ""
        lines = [f"  • {content}" for _, content in pins]
        return "Active context:\n" + "\n".join(lines)

    # ═════════════════════════════════════════════
    # KEY-VALUE STORE (for settings, modes, etc.)
    # ═════════════════════════════════════════════

    def kv_set(self, key: str, value: str):
        self._conn.execute(
            "INSERT OR REPLACE INTO kv(key, value) VALUES(?,?)",
            (key, value)
        )
        self._conn.commit()

    def kv_get(self, key: str, default: str = None) -> str:
        row = self._conn.execute(
            "SELECT value FROM kv WHERE key=?", (key,)
        ).fetchone()
        return row[0] if row else default

    # ═════════════════════════════════════════════
    # WRITE
    # ═════════════════════════════════════════════

    def add(self, role: str, content: str, skill: str = None,
            outcome: str = None, duration_ms: int = None):
        """Add a turn to all memory tiers."""
        # Tier 1 — short term
        self._short.append({"role": role, "content": content})

        # Tier 2 — episodic SQLite (with profile)
        self._conn.execute(
            "INSERT INTO episodes(ts, role, task, skill, outcome, duration, profile) "
            "VALUES(?,?,?,?,?,?,?)",
            (datetime.now().isoformat(), role, content,
             skill, outcome, duration_ms, self.profile)
        )

        # Stats update
        if skill:
            self._conn.execute(
                "INSERT INTO stats(skill, uses, success) VALUES(?,1,?) "
                "ON CONFLICT(skill) DO UPDATE SET "
                "uses=uses+1, success=success+?",
                (skill,
                 1 if outcome == "success" else 0,
                 1 if outcome == "success" else 0)
            )

        self._conn.commit()

        # Auto-compress every 100 episodes
        count = self._conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE profile=?",
            (self.profile,)
        ).fetchone()[0]
        if count > 0 and count % 100 == 0:
            self._summarise_old()

    def forget(self, target: str = "last"):
        """Delete memories. target: 'last', 'all', or keyword."""
        if target == "last":
            if self._short:
                self._short.pop()
            self._conn.execute(
                "DELETE FROM episodes WHERE id = "
                "(SELECT MAX(id) FROM episodes WHERE profile=?)",
                (self.profile,)
            )
        elif target == "all":
            self._short.clear()
            self._conn.execute(
                "DELETE FROM episodes WHERE profile=?", (self.profile,)
            )
            self._conn.execute(
                "DELETE FROM summaries WHERE profile=?", (self.profile,)
            )
        else:
            self._conn.execute(
                "DELETE FROM episodes WHERE task LIKE ? AND profile=?",
                (f"%{target}%", self.profile)
            )
        self._conn.commit()

    # ═════════════════════════════════════════════
    # READ
    # ═════════════════════════════════════════════

    def short_term(self) -> list:
        """Tier 1 — recent turns for LLM context."""
        return list(self._short)

    def recall(self, query: str, n: int = 5) -> str:
        """
        Tier 2 keyword recall with relevance scoring.
        Searches current profile + 'default' profile.
        """
        results = []
        seen = set()

        # Extract meaningful words (length > 3)
        words = [w for w in query.lower().split() if len(w) > 3]

        for word in words[:4]:
            rows = self._conn.execute(
                "SELECT ts, task, skill, outcome FROM episodes "
                "WHERE task LIKE ? AND profile IN (?, 'default') "
                "ORDER BY id DESC LIMIT 5",
                (f"%{word}%", self.profile)
            ).fetchall()

            for r in rows:
                entry = f"[{r[0][:10]}] {r[1][:80]}"
                if r[2]:
                    entry += f" (skill: {r[2]}, outcome: {r[3]})"
                if entry not in seen:
                    seen.add(entry)
                    # Score: more matching words = higher relevance
                    score = sum(1 for w in words if w in r[1].lower())
                    results.append((score, entry))

        # Also check summaries
        for word in words[:2]:
            srows = self._conn.execute(
                "SELECT summary FROM summaries "
                "WHERE summary LIKE ? AND profile IN (?, 'default') "
                "ORDER BY id DESC LIMIT 2",
                (f"%{word}%", self.profile)
            ).fetchall()
            for r in srows:
                entry = f"[summary] {r[0][:100]}"
                if entry not in seen:
                    seen.add(entry)
                    results.append((0, entry))

        if not results:
            return ""

        # Sort by relevance score
        results.sort(key=lambda x: -x[0])
        top = [entry for _, entry in results[:n]]
        return "Past relevant tasks:\n" + "\n".join(f"  • {r}" for r in top)

    def get_history(self, n: int = 20) -> list:
        """Get last n episodes as list of tuples."""
        return self._conn.execute(
            "SELECT ts, task, skill, outcome FROM episodes "
            "WHERE role='user' AND profile=? ORDER BY id DESC LIMIT ?",
            (self.profile, n)
        ).fetchall()

    def get_stats(self) -> dict:
        """Get usage stats."""
        total = self._conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE profile=?",
            (self.profile,)
        ).fetchone()[0]

        total_all = self._conn.execute(
            "SELECT COUNT(*) FROM episodes"
        ).fetchone()[0]

        top_skills = self._conn.execute(
            "SELECT skill, uses, success FROM stats "
            "ORDER BY uses DESC LIMIT 15"
        ).fetchall()

        # Provider stats from usage.log
        providers = {}
        total_tokens = 0
        usage_log = self._db_path.parent / "usage.log"
        if usage_log.exists():
            try:
                for line in usage_log.read_text().splitlines()[-500:]:
                    entry = json.loads(line)
                    prov = entry.get("provider", "?")
                    toks = entry.get("tokens", 0)
                    providers[prov] = providers.get(prov, 0) + toks
                    total_tokens += toks
            except Exception:
                pass

        # RAM usage
        ram_mb = 0
        try:
            import resource
            ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
        except Exception:
            try:
                with open(f"/proc/{os.getpid()}/status") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            ram_mb = int(line.split()[1]) // 1024
                            break
            except Exception:
                pass

        return {
            "total": total,
            "total_all": total_all,
            "top_skills": top_skills,
            "providers": providers,
            "total_tokens": total_tokens,
            "ram_mb": ram_mb,
            "profile": self.profile,
            "profiles": self.list_profiles(),
            "db_size_mb": round(self._db_path.stat().st_size / 1024 / 1024, 2)
                          if self._db_path.exists() else 0,
        }

    # ═════════════════════════════════════════════
    # MAINTENANCE
    # ═════════════════════════════════════════════

    def vacuum(self):
        """Compact the database. Run periodically."""
        self._conn.execute("VACUUM")
        self._conn.commit()

    def get_db_size(self) -> str:
        """Get database file size."""
        if self._db_path.exists():
            size = self._db_path.stat().st_size
            for unit in ("B", "KB", "MB"):
                if size < 1024:
                    return f"{size:.1f}{unit}"
                size /= 1024
        return "0B"

    # ═════════════════════════════════════════════
    # INTERNAL
    # ═════════════════════════════════════════════

    def _summarise_old(self):
        """Compress oldest 50 episodes into a summary row."""
        rows = self._conn.execute(
            "SELECT id, task, skill FROM episodes "
            "WHERE profile=? ORDER BY id ASC LIMIT 50",
            (self.profile,)
        ).fetchall()

        if len(rows) < 20:
            return

        summary = "Past session: " + "; ".join(
            f"{r[1][:40]} (skill: {r[2]})"
            for r in rows if r[2]
        )

        ids = [r[0] for r in rows]
        placeholders = ",".join("?" * len(ids))

        self._conn.execute(
            "INSERT INTO summaries(ts, summary, profile) VALUES(?,?,?)",
            (datetime.now().isoformat(), summary, self.profile)
        )
        self._conn.execute(
            f"DELETE FROM episodes WHERE id IN ({placeholders})",
            ids
        )
        self._conn.commit()

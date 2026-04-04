"""
JARVIS v2 — tools/target_context.py
Persistent target context — never lose the target mid-session.
"""
import json
import re
from pathlib import Path

CONTEXT_FILE = Path("memory/target_context.json")

class TargetContext:
    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        if CONTEXT_FILE.exists():
            try:
                return json.loads(CONTEXT_FILE.read_text())
            except Exception:
                pass
        return {"target": None, "scope": [], "history": []}

    def _save(self):
        CONTEXT_FILE.parent.mkdir(exist_ok=True)
        CONTEXT_FILE.write_text(json.dumps(self._data, indent=2))

    def set_target(self, target: str):
        target = re.sub(r'^https?://', '', target).strip().rstrip('/')
        # Keep full subdomain — don't strip it
        target = target.split('/')[0]  # remove paths but keep subdomains
        self._data["target"] = target
        if target not in self._data["history"]:
            self._data["history"].append(target)
        self._save()

    def get_target(self) -> str | None:
        return self._data.get("target")

    def inject_into_query(self, query: str) -> str:
        target = self.get_target()
        if not target:
            return query
        query = re.sub(
            r'\blocalhost\b|127\.0\.0\.1|0\.0\.0\.0',
            target,
            query,
            flags=re.IGNORECASE
        )
        recon_keywords = ["scan","recon","enum","fuzz","check","test","find"]
        has_domain = bool(re.search(r'\b[\w\-]+\.[a-z]{2,}\b', query))
        if any(kw in query.lower() for kw in recon_keywords) and not has_domain:
            query += f" on {target}"
        return query

    def clear(self):
        self._data = {"target": None, "scope": [], "history": []}
        self._save()

    def show(self) -> str:
        t = self._data.get("target", "none")
        h = self._data.get("history", [])
        return f"Target: {t}\nHistory: {', '.join(h) if h else 'none'}"

_ctx = TargetContext()

def get_target_context() -> TargetContext:
    return _ctx

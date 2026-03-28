"""
JARVIS v2 — tools/maintenance.py

Scheduled maintenance tasks:
  backup memory     Backup SQLite database
  clear cache       Clear Python bytecode cache
  vacuum db         Compact the database
  cleanup logs      Trim old logs
"""
import shutil
import time
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.text import Text


BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)


class MaintenanceTools:
    def __init__(self, console: Console, memory=None):
        self.console = console
        self.memory = memory

    async def execute(self, query: str) -> str:
        ql = query.lower().strip()

        if ql in ("backup memory", "backup", "backup db"):
            return self.backup_memory()

        if ql in ("clear cache", "clearcache", "cache clear"):
            return self.clear_cache()

        if ql in ("vacuum db", "vacuum", "compact db"):
            return self.vacuum_db()

        if ql in ("cleanup logs", "clean logs", "trim logs"):
            return self.cleanup_logs()

        if ql in ("maintenance", "maintain"):
            self.backup_memory()
            self.clear_cache()
            self.vacuum_db()
            self.cleanup_logs()
            return "Full maintenance complete"

        return f"Unknown: {query}. Try: backup memory, clear cache, vacuum db, cleanup logs"

    def backup_memory(self) -> str:
        db_path = Path("memory/history.db")
        if not db_path.exists():
            self.console.print("  [dim]No database to backup[/dim]\n")
            return "No DB"

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"history_{ts}.db"
        shutil.copy2(db_path, backup_path)
        size = backup_path.stat().st_size

        for unit in ("B", "KB", "MB"):
            if size < 1024:
                size_str = f"{size:.0f}{unit}"
                break
            size /= 1024
        else:
            size_str = f"{size:.0f}GB"

        self.console.print(f"  [bold #10b981]✓ Backup:[/bold #10b981] {backup_path} ({size_str})\n")

        # Keep only last 5 backups
        backups = sorted(BACKUP_DIR.glob("history_*.db"), reverse=True)
        for old in backups[5:]:
            old.unlink()

        return f"Backed up: {backup_path}"

    def clear_cache(self) -> str:
        count = 0
        for cache_dir in Path(".").rglob("__pycache__"):
            if ".venv" not in str(cache_dir):
                shutil.rmtree(cache_dir, ignore_errors=True)
                count += 1

        self.console.print(f"  [bold #10b981]✓ Cleared {count} __pycache__ dirs[/bold #10b981]\n")
        return f"Cleared {count} cache dirs"

    def vacuum_db(self) -> str:
        if self.memory:
            before = Path("memory/history.db").stat().st_size if Path("memory/history.db").exists() else 0
            self.memory.vacuum()
            after = Path("memory/history.db").stat().st_size if Path("memory/history.db").exists() else 0
            saved = before - after
            self.console.print(f"  [bold #10b981]✓ Database compacted[/bold #10b981]")
            if saved > 0:
                self.console.print(f"  [dim]Saved {saved} bytes[/dim]")
            self.console.print()
            return f"Vacuumed (saved {saved} bytes)"
        return "No memory instance"

    def cleanup_logs(self) -> str:
        usage_log = Path("memory/usage.log")
        router_log = Path("memory/router.log")
        trimmed = 0

        for log_file in [usage_log, router_log]:
            if log_file.exists():
                lines = log_file.read_text().splitlines()
                if len(lines) > 1000:
                    # Keep last 500 lines
                    log_file.write_text("\n".join(lines[-500:]) + "\n")
                    trimmed += len(lines) - 500

        self.console.print(f"  [bold #10b981]✓ Trimmed {trimmed} old log entries[/bold #10b981]\n")
        return f"Trimmed {trimmed} log entries"


MAINTENANCE_COMMANDS = (
    "backup memory", "backup db", "backup",
    "clear cache", "clearcache", "cache clear",
    "vacuum db", "vacuum", "compact db",
    "cleanup logs", "clean logs", "trim logs",
    "maintenance", "maintain",
)


def is_maintenance_command(query: str) -> bool:
    return query.lower().strip() in MAINTENANCE_COMMANDS

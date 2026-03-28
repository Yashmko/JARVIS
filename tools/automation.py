"""
JARVIS v2 — tools/automation.py

Task Queue, Cron Jobs, Clipboard, Git Integration.

Commands:
  queue: <task>           Add task to queue
  queue list              Show queued tasks
  queue clear             Clear queue
  run queue               Execute all queued tasks
  
  every <N> <unit> run: <cmd>   Schedule recurring task
  cron list               Show scheduled tasks
  cron clear              Clear all cron jobs
  
  clipboard copy <text>   Copy to clipboard
  clipboard paste         Paste from clipboard
  
  git status              Git status
  git diff                Show diff
  git commit <msg>        Commit all with message
  git push                Push to remote
  git pull                Pull from remote
  git branch <name>       Create and switch branch
  git log                 Show recent commits
  
  chain: skill1 > skill2 > skill3    Create custom workflow
"""
import asyncio
import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.text import Text
from rich.table import Table


@dataclass
class AutoResult:
    success: bool
    output: str = ""
    error: str = ""


class TaskQueue:
    """Simple task queue — queue tasks, then run them all."""

    def __init__(self):
        self.tasks: list[str] = []

    def add(self, task: str):
        self.tasks.append(task)

    def clear(self):
        self.tasks.clear()

    def list_tasks(self) -> list[str]:
        return list(self.tasks)

    def pop_all(self) -> list[str]:
        tasks = list(self.tasks)
        self.tasks.clear()
        return tasks


class CronManager:
    """In-memory recurring tasks. Runs as asyncio background tasks."""

    def __init__(self):
        self.jobs: list[dict] = []
        self._running_tasks: list[asyncio.Task] = []

    def add(self, cmd: str, interval_seconds: int, label: str):
        job = {
            "cmd": cmd,
            "interval": interval_seconds,
            "label": label,
            "created": datetime.now().isoformat(),
            "runs": 0,
        }
        self.jobs.append(job)
        return job

    def clear(self):
        for task in self._running_tasks:
            task.cancel()
        self._running_tasks.clear()
        self.jobs.clear()

    def list_jobs(self) -> list[dict]:
        return list(self.jobs)

    async def start_job(self, job: dict, executor_fn):
        """Run a job on interval as background task."""
        async def _loop():
            while True:
                await asyncio.sleep(job["interval"])
                job["runs"] += 1
                await executor_fn(job["cmd"])

        task = asyncio.create_task(_loop())
        self._running_tasks.append(task)


class AutomationTools:
    def __init__(self, console: Console):
        self.console = console
        self.queue = TaskQueue()
        self.cron = CronManager()

    async def execute(self, query: str, run_fn=None) -> AutoResult:
        q = query.strip()
        ql = q.lower()

        # ── TASK QUEUE ────────────────────────────
        if ql.startswith("queue:") or ql.startswith("queue add"):
            task = q.split(":", 1)[1].strip() if ":" in q else q.replace("queue add", "").strip()
            self.queue.add(task)
            count = len(self.queue.list_tasks())
            self.console.print(f"  [bold #10b981]✓ Queued ({count} total):[/bold #10b981] {task}\n")
            return AutoResult(True, output=f"Queued: {task}")

        if ql == "queue list" or ql == "queue":
            tasks = self.queue.list_tasks()
            if not tasks:
                self.console.print("  [dim]Queue is empty.[/dim]\n")
                return AutoResult(True, output="Empty queue")
            t = Table(title=f"Task Queue ({len(tasks)})", border_style="dim #374151")
            t.add_column("#", style="dim", justify="right")
            t.add_column("Task", style="#5eead4")
            for i, task in enumerate(tasks, 1):
                t.add_row(str(i), task)
            self.console.print()
            self.console.print(t)
            self.console.print()
            return AutoResult(True, output="\n".join(tasks))

        if ql == "queue clear":
            self.queue.clear()
            self.console.print("  [dim]✓ Queue cleared[/dim]\n")
            return AutoResult(True, output="Queue cleared")

        if ql == "run queue":
            tasks = self.queue.pop_all()
            if not tasks:
                self.console.print("  [dim]Queue is empty.[/dim]\n")
                return AutoResult(True, output="Nothing to run")

            self.console.print(Text(f"\n  🔄 Running {len(tasks)} queued tasks...\n",
                                   style="bold #a78bfa"))
            results = []
            for i, task in enumerate(tasks, 1):
                self.console.print(Text(f"  ── Task {i}/{len(tasks)}: {task}", style="bold #f59e0b"))
                if run_fn:
                    await run_fn(task)
                results.append(task)
                self.console.print()

            self.console.print(Text(f"  ✓ {len(results)} tasks completed\n", style="bold #10b981"))
            return AutoResult(True, output=f"Ran {len(results)} tasks")

        # ── CRON JOBS ─────────────────────────────
        if ql.startswith("every "):
            return await self._parse_cron(q, run_fn)

        if ql == "cron list" or ql == "cron":
            jobs = self.cron.list_jobs()
            if not jobs:
                self.console.print("  [dim]No scheduled jobs.[/dim]\n")
                return AutoResult(True, output="No cron jobs")
            t = Table(title=f"Scheduled Jobs ({len(jobs)})", border_style="dim #374151")
            t.add_column("#", style="dim", justify="right")
            t.add_column("Command", style="#5eead4")
            t.add_column("Interval", style="#f59e0b")
            t.add_column("Runs", justify="right", style="dim")
            for i, job in enumerate(jobs, 1):
                interval = job["interval"]
                if interval >= 3600:
                    label = f"{interval // 3600}h"
                elif interval >= 60:
                    label = f"{interval // 60}m"
                else:
                    label = f"{interval}s"
                t.add_row(str(i), job["cmd"], label, str(job["runs"]))
            self.console.print()
            self.console.print(t)
            self.console.print()
            return AutoResult(True)

        if ql == "cron clear":
            self.cron.clear()
            self.console.print("  [dim]✓ All cron jobs cancelled[/dim]\n")
            return AutoResult(True, output="Cron cleared")

        # ── CLIPBOARD ─────────────────────────────
        if ql.startswith("clipboard copy ") or ql.startswith("clip copy "):
            text = q.split(" ", 2)[2].strip().strip("\"'") if len(q.split(" ")) > 2 else ""
            return self.clipboard_write(text)

        if ql in ("clipboard paste", "clipboard", "clip paste", "clip"):
            return self.clipboard_read()

        # ── GIT ───────────────────────────────────
        if ql.startswith("git "):
            return await self.git_command(q)

        # ── CHAIN ─────────────────────────────────
        if ql.startswith("chain:") or ql.startswith("chain "):
            return self.create_chain(q)

        return AutoResult(False, error=f"Unknown automation command: '{q}'")

    # ── CRON PARSER ───────────────────────────────
    async def _parse_cron(self, query: str, run_fn) -> AutoResult:
        """Parse: every 5 minutes run: backup memory"""
        import re
        m = re.search(r'every\s+(\d+)\s+(second|minute|hour|day)s?\s+run:\s*(.+)',
                      query, re.IGNORECASE)
        if not m:
            return AutoResult(False, error='Format: every <N> <seconds/minutes/hours> run: <command>')

        amount = int(m.group(1))
        unit = m.group(2).lower()
        cmd = m.group(3).strip()

        seconds = amount * {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[unit]

        job = self.cron.add(cmd, seconds, f"every {amount} {unit}(s)")

        if run_fn:
            await self.cron.start_job(job, run_fn)

        self.console.print(
            Text(f"  ⏱ Scheduled: '{cmd}' every {amount} {unit}(s)\n", style="dim #f59e0b")
        )
        return AutoResult(True, output=f"Cron job created: {cmd}")

    # ── CLIPBOARD ─────────────────────────────────
    def clipboard_write(self, text: str) -> AutoResult:
        try:
            for cmd in [["xclip", "-selection", "clipboard"],
                       ["xsel", "--clipboard", "--input"],
                       ["wl-copy"]]:
                if shutil.which(cmd[0]):
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    proc.communicate(text.encode())
                    self.console.print(f"  [bold #10b981]✓ Copied:[/bold #10b981] {text[:60]}\n")
                    return AutoResult(True, output=f"Copied: {text[:60]}")
            return AutoResult(False, error="No clipboard tool (install xclip or xsel)")
        except Exception as e:
            return AutoResult(False, error=str(e))

    def clipboard_read(self) -> AutoResult:
        try:
            for cmd in [["xclip", "-selection", "clipboard", "-o"],
                       ["xsel", "--clipboard", "--output"],
                       ["wl-paste"]]:
                if shutil.which(cmd[0]):
                    r = subprocess.run(cmd, capture_output=True, text=True)
                    content = r.stdout.strip()
                    self.console.print(f"  [dim]Clipboard:[/dim] {content[:200]}\n")
                    return AutoResult(True, output=content)
            return AutoResult(False, error="No clipboard tool (install xclip or xsel)")
        except Exception as e:
            return AutoResult(False, error=str(e))

    # ── GIT ───────────────────────────────────────
    async def git_command(self, query: str) -> AutoResult:
        parts = query.strip().split(" ", 2)
        sub = parts[1] if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else ""

        git_cmds = {
            "status": ["git", "status", "--short"],
            "diff": ["git", "diff", "--stat"],
            "log": ["git", "log", "--oneline", "-10"],
            "pull": ["git", "pull"],
            "push": ["git", "push"],
            "stash": ["git", "stash"],
            "stash pop": ["git", "stash", "pop"],
        }

        if sub == "commit":
            msg = arg.strip().strip("\"'") or "Update from Jarvis"
            cmd = ["git", "add", "-A"]
            r1 = subprocess.run(cmd, capture_output=True, text=True)
            cmd2 = ["git", "commit", "-m", msg]
            r2 = subprocess.run(cmd2, capture_output=True, text=True)
            output = r1.stdout + r2.stdout + r2.stderr
            self.console.print(Text(f"  {output.strip()}\n", style="#9ca3af"))
            return AutoResult(r2.returncode == 0, output=output.strip(),
                            error=r2.stderr if r2.returncode != 0 else "")

        if sub == "branch":
            name = arg.strip()
            if not name:
                return AutoResult(False, error="Usage: git branch <name>")
            r = subprocess.run(["git", "checkout", "-b", name],
                             capture_output=True, text=True)
            output = r.stdout + r.stderr
            self.console.print(Text(f"  {output.strip()}\n", style="#9ca3af"))
            return AutoResult(r.returncode == 0, output=output.strip())

        if sub in git_cmds:
            cmd = git_cmds[sub]
            r = subprocess.run(cmd, capture_output=True, text=True)
            output = r.stdout.strip()
            if output:
                self.console.print(Text(f"  {output}\n", style="#9ca3af"))
            else:
                self.console.print(f"  [dim]Nothing to show[/dim]\n")
            return AutoResult(True, output=output)

        # Pass through any git command
        cmd = query.strip().split()
        r = subprocess.run(cmd, capture_output=True, text=True)
        output = (r.stdout + r.stderr).strip()
        self.console.print(Text(f"  {output}\n", style="#9ca3af"))
        return AutoResult(r.returncode == 0, output=output)

    # ── SKILL CHAINS ──────────────────────────────
    def create_chain(self, query: str) -> AutoResult:
        """Parse: chain: scan > exploit > report"""
        chain_str = query.replace("chain:", "").replace("chain ", "").strip()
        skills = [s.strip() for s in chain_str.replace(">", "→").replace("→", "|").split("|")]
        skills = [s for s in skills if s]

        if not skills:
            return AutoResult(False, error="Usage: chain: skill1 > skill2 > skill3")

        # Create workflow JSON
        name = "-".join(skills[:3])
        workflow = {
            "name": f"Custom: {name}",
            "description": f"Custom chain: {' → '.join(skills)}",
            "triggers": [f"run chain {name}", name],
            "steps": [
                {"skill": skill, "label": skill.replace("-", " ").title()}
                for skill in skills
            ],
        }

        # Save to workflows/
        wf_path = Path("workflows") / f"custom_{name}.json"
        wf_path.write_text(json.dumps(workflow, indent=2))

        self.console.print(Text(f"\n  ✓ Chain created: {' → '.join(skills)}", style="bold #10b981"))
        self.console.print(Text(f"  Saved: {wf_path}", style="dim #6b7280"))
        self.console.print(Text(f"  Trigger: \"{workflow['triggers'][0]}\"\n", style="dim #5eead4"))

        return AutoResult(True, output=f"Chain created: {wf_path}")


# ── KEYWORD DETECTOR ──────────────────────────────

AUTOMATION_PREFIXES = (
    "queue:", "queue ", "run queue",
    "every ", "cron ",
    "clipboard", "clip ",
    "git ",
    "chain:", "chain ",
)


def is_automation_command(query: str) -> bool:
    ql = query.lower().strip()
    return any(ql.startswith(p) for p in AUTOMATION_PREFIXES)

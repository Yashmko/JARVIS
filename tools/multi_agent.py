"""
JARVIS v2 — tools/multi_agent.py
Multi-agent mode — splits tasks and executes with real shell.
"""
import asyncio
import json
import re
from rich.console import Console
from rich.text import Text

MULTI_PREFIXES = ("multi:", "agents:", "multi ", "agents ")

def is_multi_command(query: str) -> bool:
    ql = query.lower().strip()
    return any(ql.startswith(p) for p in MULTI_PREFIXES)

class MultiAgent:
    def __init__(self, console: Console, brain, router, memory, settings, persona,
                 stream_fn, build_messages_fn):
        self.console = console
        self.brain = brain
        self.router = router
        self.memory = memory
        self.settings = settings
        self.persona = persona
        self.stream_fn = stream_fn
        self.build_messages_fn = build_messages_fn

    async def execute(self, query: str) -> str:
        from tools.shell_executor import ShellExecutor
        from tools.target_context import get_target_context

        task = query.lower()
        for prefix in MULTI_PREFIXES:
            task = task.replace(prefix, "", 1)
        task = task.strip()

        self.console.print(Text(f"\n🤖 Multi-Agent Mode: {task}\n", style="bold #a78bfa"))

        tctx = get_target_context()
        target = tctx.get_target()

        # Extract target from query if present
        dm = re.search(r"[\w\-]+\.(?:com|org|net|io|co|app|dev|gov|edu|uk)", query)
        if dm and "example.com" not in dm.group(0):
            target = dm.group(0)
            tctx.set_target(target)

        shell = ShellExecutor(self.console)

        # Recon tasks — run real tools
        task_lower = task.lower()

        if any(w in task_lower for w in ["subdomain", "recon", "enumerate", "find host", "alive"]):
            if target:
                self.console.print(Text(f"\n── Agent 1: Subdomain Enumeration ──", style="bold #f59e0b"))
                await shell.execute(f"!subfinder -d {target} -silent | head -30")
                self.console.print(Text(f"\n── Agent 2: Alive Check ──", style="bold #f59e0b"))
                await shell.execute(f"!subfinder -d {target} -silent | httpx -silent -sc -title 2>/dev/null | head -20")
            else:
                self.console.print("  [yellow]No target set. Use: target example.com[/yellow]\n")
            return "multi-agent recon complete"

        if any(w in task_lower for w in ["vuln", "scan", "nuclei", "security"]):
            if target:
                self.console.print(Text(f"\n── Agent 1: Port Scan ──", style="bold #f59e0b"))
                await shell.execute(f"!nmap -sV --top-ports 50 -T4 {target}")
                self.console.print(Text(f"\n── Agent 2: Vuln Scan ──", style="bold #f59e0b"))
                await shell.execute(f"!nuclei -u https://{target} -severity medium,high,critical -silent")
            else:
                self.console.print("  [yellow]No target set. Use: target example.com[/yellow]\n")
            return "multi-agent vuln scan complete"

        if any(w in task_lower for w in ["api", "endpoint", "rest"]):
            if target:
                self.console.print(Text(f"\n── Agent 1: API Discovery ──", style="bold #f59e0b"))
                await shell.execute(f"!curl -s https://{target}/api/ -I")
                await shell.execute(f"!curl -s https://{target}/v1/ -I")
                await shell.execute(f"!curl -s https://{target}/graphql -I")
                self.console.print(Text(f"\n── Agent 2: Wayback URLs ──", style="bold #f59e0b"))
                await shell.execute(f"!waybackurls {target} 2>/dev/null | grep -E '/api/|/v[0-9]/' | sort -u | head -20")
            else:
                self.console.print("  [yellow]No target set.[/yellow]\n")
            return "multi-agent api discovery complete"

        # Generic — ask LLM to split then execute each subtask
        self.console.print(Text("  Splitting task with LLM...\n", style="dim"))
        split_prompt = [{
            "role": "system",
            "content": (
                "Split this task into 2-4 subtasks. "
                "Respond ONLY with JSON: {\"subtasks\": [\"task1\", \"task2\"]}"
            )
        }, {
            "role": "user",
            "content": f"Split: {task}"
        }]

        try:
            resp = await self.brain.complete(split_prompt)
            clean = re.sub(r'```(?:json)?\n?', '', resp).strip().rstrip('`')
            data = json.loads(clean)
            subtasks = data.get("subtasks", [task])[:4]
        except Exception:
            subtasks = [task]

        all_outputs = []
        for i, subtask in enumerate(subtasks, 1):
            self.console.print(Text(f"\n── Agent {i}/{len(subtasks)}: {subtask[:60]}", style="bold #f59e0b"))
            match = self.router.route(subtask)
            msgs = self.build_messages_fn(subtask, self.memory, self.persona,
                                          skill=match, settings=self.settings)
            out = await self.stream_fn(msgs, self.brain)
            all_outputs.append(out)
            self.memory.add("user", subtask,
                          skill=match["name"] if match else None,
                          outcome="success")

        self.console.print(Text(f"\n✓ All {len(subtasks)} agents complete\n", style="bold #10b981"))
        return "\n\n".join(all_outputs)

"""
JARVIS v2 — tools/multi_agent.py

Lightweight multi-agent mode.
Splits complex tasks into sub-agents that each handle one aspect.

Usage:
  multi: analyze this codebase for security and performance
  agents: plan a SaaS, design it, and write the code

How it works:
  1. Brain splits the task into 2-4 sub-tasks
  2. Each sub-task runs through classify→route→execute
  3. Results are combined into a final summary
"""
import asyncio
import json
import re
from rich.console import Console
from rich.text import Text
from rich.table import Table


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
        """Split task into sub-agents and execute each."""
        # Remove prefix
        task = query.lower().replace("multi:", "").replace("agents:", "").strip()

        self.console.print(Text(f"\n  🤖 Multi-Agent Mode: Splitting task...\n", style="bold #a78bfa"))

        # Ask brain to split the task
        split_prompt = [{
            "role": "system",
            "content": (
                "You split complex tasks into 2-4 independent sub-tasks.\n"
                "Respond ONLY with JSON: {\"subtasks\": [\"task1\", \"task2\", ...]}\n"
                "Each subtask should be a clear, actionable instruction.\n"
                "Max 4 subtasks."
            )
        }, {
            "role": "user",
            "content": f"Split this task: {task}"
        }]

        try:
            resp = await self.brain.complete(split_prompt)
            clean = re.sub(r'```(?:json)?\n?', '', resp).strip().rstrip('```').strip()
            data = json.loads(clean)
            subtasks = data.get("subtasks", [task])[:4]
        except Exception:
            subtasks = [task]

        if len(subtasks) <= 1:
            self.console.print("  [dim]Single task — running directly.[/dim]\n")
            subtasks = [task]

        # Show plan
        self.console.print(Text(f"  Agents: {len(subtasks)}", style="bold #f59e0b"))
        for i, st in enumerate(subtasks, 1):
            self.console.print(f"  [dim]  {i}. {st}[/dim]")
        self.console.print()

        # Execute each subtask
        all_outputs = []
        for i, subtask in enumerate(subtasks, 1):
            self.console.print(Text(f"\n  ── Agent {i}/{len(subtasks)}: {subtask[:60]}", style="bold #f59e0b"))
            self.console.print()

            # Route subtask
            try:
                cls = await self.brain.classify(subtask)
                hint = cls.get("category_hint", "general")
            except Exception:
                hint = "general"

            match = self.router.route(subtask, category_hint=hint)

            if match:
                self.console.print(f"  [dim]Skill: {match['name']} ({match.get('score',0):.0%})[/dim]")

            msgs = self.build_messages_fn(
                subtask, self.memory, self.persona,
                skill=match, settings=self.settings
            )

            out = await self.stream_fn(msgs, self.brain)
            all_outputs.append(f"## Agent {i}: {subtask}\n{out}")

            self.console.print(f"  [bold #10b981]✓ Agent {i} complete[/bold #10b981]")

            self.memory.add("user", subtask,
                          skill=match["name"] if match else None,
                          outcome="success")

        # Summary
        combined = "\n\n".join(all_outputs)

        self.console.print(Text(f"\n  ✓ All {len(subtasks)} agents complete\n", style="bold #10b981"))

        return combined


MULTI_PREFIXES = ("multi:", "agents:", "multi ", "agents ")

def is_multi_command(query: str) -> bool:
    ql = query.lower().strip()
    return any(ql.startswith(p) for p in MULTI_PREFIXES)

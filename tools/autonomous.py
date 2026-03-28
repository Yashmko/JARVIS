"""
JARVIS v2 — tools/autonomous.py

Autonomous execution loop.
Jarvis runs commands, reads output, analyzes, and keeps going.

Usage:
  auto: scan example.com for all vulnerabilities
  autonomous: find and fix bugs in my code
  agent: do a complete security assessment of example.com

How it works:
1. Brain creates a plan (list of commands to run)
2. Each command executes via system_control
3. Output is fed back to brain for analysis
4. Brain decides next action or stops
5. Max 10 iterations (safety limit)
"""
import asyncio
import json
import re
from rich.console import Console
from rich.text import Text


MAX_ITERATIONS = 10


class AutonomousAgent:
    def __init__(self, console: Console, brain, sys_ctrl, memory, settings, persona):
        self.console = console
        self.brain = brain
        self.sys_ctrl = sys_ctrl
        self.memory = memory
        self.settings = settings
        self.persona = persona

    async def execute(self, query: str) -> str:
        task = query.lower()
        for prefix in ("auto:", "autonomous:", "agent:", "auto ", "autonomous ", "agent "):
            task = task.replace(prefix, "", 1)
        task = task.strip()

        self.console.print(Text(f"\n  🤖 Autonomous Mode", style="bold #ef4444"))
        self.console.print(Text(f"  Task: {task}", style="bold white"))
        self.console.print(Text(f"  Max iterations: {MAX_ITERATIONS}", style="dim"))
        self.console.print(Text(f"  {'═' * 50}\n", style="dim #374151"))

        # Confirm before starting
        self.console.print(Text("  ⚠ Autonomous mode will run commands on your system.",
                               style="bold #f59e0b"))
        self.console.print(Text("  Type 'yes' to proceed: ", style="dim"), end="")

        try:
            resp = await asyncio.get_event_loop().run_in_executor(None, input)
            if resp.strip().lower() not in ("yes", "y"):
                self.console.print("  [dim]Cancelled.[/dim]\n")
                return "Cancelled"
        except Exception:
            return "Cancelled"

        self.console.print()

        context = f"Task: {task}\n"
        all_outputs = []

        for iteration in range(1, MAX_ITERATIONS + 1):
            self.console.print(Text(f"  ── Iteration {iteration}/{MAX_ITERATIONS} ──",
                                   style="bold #f59e0b"))

            # Ask brain what to do next
            plan_prompt = [{
                "role": "system",
                "content": (
                    "You are an autonomous agent executing a task step by step.\n"
                    "Based on the context, decide the NEXT action.\n\n"
                    "Respond with JSON:\n"
                    '{"action": "command", "command": "the shell command to run"}\n'
                    "OR\n"
                    '{"action": "analyze", "analysis": "your analysis of results"}\n'
                    "OR\n"
                    '{"action": "done", "summary": "final summary of everything done"}\n\n'
                    "Rules:\n"
                    "- Only run SAFE commands (curl, nmap, grep, cat, ls, etc.)\n"
                    "- NEVER run destructive commands (rm, dd, mkfs, etc.)\n"
                    "- If you have enough info, action=done\n"
                    "- Be efficient — don't repeat commands\n"
                    "- Max 10 iterations total"
                )
            }, {
                "role": "user",
                "content": context
            }]

            try:
                resp = await self.brain.complete(plan_prompt)
                clean = re.sub(r'```(?:json)?\n?', '', resp).strip().rstrip('```').strip()
                action = json.loads(clean)
            except Exception as e:
                self.console.print(f"  [dim]Brain error: {e}. Stopping.[/dim]\n")
                break

            act = action.get("action", "done")

            if act == "command":
                cmd = action.get("command", "")
                if not cmd:
                    continue

                # Safety check
                dangerous = ["rm ", "dd ", "mkfs", "shutdown", "reboot", "> /dev/",
                            "chmod -R 777", ":()", "format "]
                if any(d in cmd.lower() for d in dangerous):
                    self.console.print(f"  [red]⛔ Blocked dangerous command: {cmd}[/red]")
                    context += f"\nIteration {iteration}: BLOCKED dangerous command: {cmd}\n"
                    continue

                self.console.print(f"  [#5eead4]$ {cmd}[/#5eead4]")

                result = await self.sys_ctrl.run_command(cmd, timeout=30)
                output = result.output[:2000] if result.output else result.error[:500]
                all_outputs.append(f"$ {cmd}\n{output}")

                context += f"\nIteration {iteration}:\nCommand: {cmd}\nOutput:\n{output[:1000]}\n"

            elif act == "analyze":
                analysis = action.get("analysis", "")
                self.console.print(f"  [dim]Analysis: {analysis[:200]}[/dim]")
                context += f"\nIteration {iteration}: Analysis: {analysis}\n"

            elif act == "done":
                summary = action.get("summary", "Task complete.")
                self.console.print(Text(f"\n  {'═' * 50}", style="dim #374151"))
                self.console.print(Text(f"  ✓ Autonomous task complete ({iteration} iterations)",
                                       style="bold #10b981"))
                self.console.print(f"\n  {summary}\n")

                self.memory.add("user", task, skill="autonomous-agent", outcome="success")
                return summary

            else:
                break

        self.console.print(Text(f"\n  ⚠ Reached max iterations ({MAX_ITERATIONS})",
                               style="bold #f59e0b"))
        self.console.print()

        final = "\n".join(all_outputs[-5:])
        self.memory.add("user", task, skill="autonomous-agent", outcome="max_iterations")
        return final


AUTO_PREFIXES = ("auto:", "autonomous:", "agent:", "auto ", "autonomous ", "agent ")

def is_auto_command(query: str) -> bool:
    ql = query.lower().strip()
    return any(ql.startswith(p) for p in AUTO_PREFIXES)

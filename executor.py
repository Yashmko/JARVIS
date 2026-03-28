"""
JARVIS v2 — executor.py (Phase B)

Upgraded:
- No duplicate text in Live display (fixed the repeating bug)
- Action enforcement — skills ACT instead of asking questions
- Better context handoff between workflow steps
- Progress tracking per step
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success:     bool
    output:      str
    error:       str | None
    skill_name:  str
    duration_ms: int
    outcome:     str


class ExecutionEngine:
    def __init__(self, settings):
        self.settings = settings

    async def run(self, skill: dict, messages: list,
                  brain, console) -> ExecutionResult:
        name    = skill.get("name", "unknown")
        timeout = skill.get("timeout", self.settings.DEFAULT_TIMEOUT)
        t0      = time.time()

        for attempt in range(self.settings.MAX_RETRIES + 1):
            try:
                output = await asyncio.wait_for(
                    self._stream_clean(messages, brain, console),
                    timeout=timeout,
                )
                ms = int((time.time() - t0) * 1000)
                outcome = "retry_success" if attempt > 0 else "success"
                return ExecutionResult(
                    success=True, output=output, error=None,
                    skill_name=name, duration_ms=ms, outcome=outcome,
                )

            except asyncio.TimeoutError:
                ms = int((time.time() - t0) * 1000)
                if attempt < self.settings.MAX_RETRIES:
                    console.print(f"  [dim]Timeout — retrying...[/dim]")
                    await asyncio.sleep(1)
                    continue
                return ExecutionResult(
                    success=False, output="",
                    error=f"Timeout after {timeout}s",
                    skill_name=name, duration_ms=ms, outcome="timeout",
                )

            except Exception as e:
                ms = int((time.time() - t0) * 1000)
                if self._is_transient(str(e)) and attempt < self.settings.MAX_RETRIES:
                    console.print(f"  [dim]Error: {e} — retrying...[/dim]")
                    await asyncio.sleep(1)
                    continue
                return ExecutionResult(
                    success=False, output="",
                    error=str(e),
                    skill_name=name, duration_ms=ms, outcome="error",
                )

        ms = int((time.time() - t0) * 1000)
        return ExecutionResult(
            success=False, output="", error="Max retries exceeded",
            skill_name=name, duration_ms=ms, outcome="error",
        )

    async def run_chain(self, skills: list, base_messages: list,
                        brain, console) -> list:
        results = []
        carry   = ""

        for skill in skills:
            msgs = list(base_messages)
            if carry:
                last = msgs[-1]["content"]
                msgs[-1] = {
                    "role": "user",
                    "content": f"{last}\n\nContext from previous step:\n{carry[:1500]}"
                }
            result = await self.run(skill, msgs, brain, console)
            results.append(result)
            carry = result.output

        return results

    async def _stream_clean(self, messages, brain, console) -> str:
        """
        Stream tokens WITHOUT the repeating text bug.
        Uses line-by-line printing instead of replacing the entire block.
        """
        output = ""
        current_line = ""

        console.print("", end="")  # Start output area

        async for chunk in brain.stream(messages):
            output += chunk
            current_line += chunk

            # Print complete lines as they come
            while "\n" in current_line:
                line, current_line = current_line.split("\n", 1)
                console.print(f"  {line}")

        # Print any remaining partial line
        if current_line.strip():
            console.print(f"  {current_line}")

        console.print()
        return output

    @staticmethod
    def _is_transient(error: str) -> bool:
        transient = ["rate limit", "503", "502", "connection", "timeout",
                     "overloaded", "try again"]
        return any(t in error.lower() for t in transient)

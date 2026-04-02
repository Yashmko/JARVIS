"""
JARVIS v2 — tools/shell_executor.py
Raw shell execution — bypasses ALL agent logic.
No NLP rewriting. No interception. No hallucination.
"""
import asyncio
import time
from dataclasses import dataclass
from rich.console import Console
from rich.text import Text

@dataclass
class ShellResult:
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0

SHELL_PASSTHROUGH = (
    "grep","cat","awk","sed","curl","httpx",
    "nmap","ffuf","subfinder","amass","nuclei",
    "dig","nslookup","whois","ping","traceroute",
    "find","ls","ps","netstat","ss","lsof",
    "head","tail","wc","sort","uniq","cut",
    "wget","python3","python","bash","sh",
    "jq","xmllint","base64","openssl","ssh",
)

def is_raw_shell_command(query: str) -> bool:
    q = query.strip()
    if q.startswith("!") or q.lower().startswith("/shell "):
        return True
    first_word = q.split()[0].lower() if q.split() else ""
    return first_word in SHELL_PASSTHROUGH

def clean_command(query: str) -> str:
    q = query.strip()
    if q.startswith("!"):
        return q[1:].strip()
    if q.lower().startswith("/shell "):
        return q[7:].strip()
    return q

class ShellExecutor:
    def __init__(self, console: Console):
        self.console = console

    async def execute(self, query: str, timeout: int = 60) -> ShellResult:
        cmd = clean_command(query)
        if not cmd:
            return ShellResult(False, error="Empty command")

        self.console.print(Text(f"\n $ {cmd}\n", style="bold #5eead4"))
        t0 = time.time()
        output_lines = []

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async def _read():
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode(errors="replace").rstrip()
                    output_lines.append(decoded)
                    self.console.print(Text(f"  {decoded}", style="#9ca3af"))

            await asyncio.wait_for(_read(), timeout=timeout)
            await proc.wait()

            ms = int((time.time() - t0) * 1000)
            full = "\n".join(output_lines)

            if not full.strip():
                full = "(no output)"
                self.console.print(Text("  (no output)\n", style="dim #6b7280"))
            else:
                self.console.print(Text(f"\n  ✓ [{ms}ms]\n", style="dim #10b981"))

            return ShellResult(
                success=(proc.returncode == 0),
                output=full,
                returncode=proc.returncode or 0,
            )

        except asyncio.TimeoutError:
            return ShellResult(False, error=f"Timed out after {timeout}s")
        except Exception as e:
            return ShellResult(False, error=str(e))

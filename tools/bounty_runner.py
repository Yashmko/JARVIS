"""
JARVIS v2 — tools/bounty_runner.py
Real bug bounty recon — runs actual tools, no LLM.
All output is from real commands only.
"""
import asyncio
import shutil
import time
from pathlib import Path
from rich.console import Console
from rich.text import Text
from rich.table import Table

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

class BountyRunner:
    def __init__(self, console: Console):
        self.console = console

    def _tool_exists(self, name: str) -> bool:
        return shutil.which(name) is not None

    async def _run(self, cmd: str, timeout: int = 60) -> str:
        """Run command, collect output, print cleanly."""
        self.console.print(Text(f"\n $ {cmd}\n", style="bold #5eead4"))
        lines = []
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            async def _read():
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode(errors="replace").rstrip()
                    lines.append(decoded)
                    if not decoded.startswith("[INF]") and decoded.strip():
                        self.console.print(Text(f"  {decoded}", style="#9ca3af"))
            await asyncio.wait_for(_read(), timeout=timeout)
            await proc.wait()
        except asyncio.TimeoutError:
            self.console.print(Text(f"  (timed out after {timeout}s)\n", style="dim #ef4444"))
        except Exception as e:
            self.console.print(Text(f"  Error: {e}\n", style="bold #ef4444"))
        output = "\n".join(lines)
        if not output.strip():
            self.console.print(Text("  (no output)\n", style="dim #6b7280"))
            return "(no output)"
        return output

    async def run_subdomains(self, target: str) -> str:
        """Run subfinder silently, save to file, show count + preview only."""
        self.console.print(Text(f"\n🔍 Subdomain Enumeration: {target}\n", style="bold #a78bfa"))
        subs_file = REPORTS_DIR / f"{target}_subs.txt"

        if self._tool_exists("subfinder"):
            self.console.print(Text(
                f"  Running subfinder... (saving to {subs_file})\n",
                style="dim #6b7280"
            ))
            try:
                proc = await asyncio.create_subprocess_shell(
                    f"subfinder -d {target} -silent -o {subs_file}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                self.console.print(Text("  (subfinder timed out)\n", style="dim #ef4444"))

            if subs_file.exists() and subs_file.stat().st_size > 0:
                out = subs_file.read_text()
                subs = [s for s in out.splitlines() if s.strip()]
                count = len(subs)
                self.console.print(Text(
                    f"  ✓ {count} subdomains found → {subs_file}\n",
                    style="bold #10b981"
                ))
                # Show first 10 only
                for s in subs[:10]:
                    self.console.print(Text(f"    {s}", style="dim #5eead4"))
                if count > 10:
                    self.console.print(Text(
                        f"    ... and {count-10} more (see {subs_file})\n",
                        style="dim #6b7280"
                    ))
                return out
            else:
                self.console.print(Text("  (no subdomains found)\n", style="dim #6b7280"))
                return "(no output)"
        else:
            self.console.print(Text(
                "  subfinder not installed.\n"
                "  Install: go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest\n"
                "  Using crt.sh fallback...\n",
                style="dim #f59e0b"
            ))
            try:
                proc = await asyncio.create_subprocess_shell(
                    f"curl -s 'https://crt.sh/?q=%.{target}&output=json' | "
                    f"python3 -c \""
                    f"import json,sys; "
                    f"[print(e['name_value']) for e in json.load(sys.stdin) "
                    f"if '*' not in e.get('name_value','')]"
                    f"\" | sort -u",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
                out = stdout.decode(errors="replace").strip()
                if out:
                    subs_file.write_text(out)
                    count = len(out.splitlines())
                    self.console.print(Text(
                        f"  ✓ {count} subdomains via crt.sh → {subs_file}\n",
                        style="bold #10b981"
                    ))
                    for s in out.splitlines()[:10]:
                        self.console.print(Text(f"    {s}", style="dim #5eead4"))
                    return out
            except Exception as e:
                self.console.print(Text(f"  crt.sh error: {e}\n", style="dim #ef4444"))
            return "(no output)"

    async def run_headers(self, target: str) -> str:
        self.console.print(Text(f"\n🔍 Security Headers: {target}\n", style="bold #a78bfa"))
        out = await self._run(
            f"curl -s -I -L --max-time 15 https://{target}",
            timeout=20
        )
        if out != "(no output)":
            security_headers = [
                "strict-transport-security",
                "content-security-policy",
                "x-frame-options",
                "x-content-type-options",
                "permissions-policy",
                "referrer-policy",
            ]
            self.console.print()
            missing = []
            for h in security_headers:
                if h in out.lower():
                    self.console.print(Text(f"  ✓ {h}", style="#10b981"))
                else:
                    missing.append(h)
                    self.console.print(Text(f"  ✗ MISSING: {h}", style="bold #ef4444"))
            if missing:
                hfile = REPORTS_DIR / f"{target}_missing_headers.txt"
                hfile.write_text("\n".join(missing))
            self.console.print()
        return out

    async def run_ports(self, target: str) -> str:
        self.console.print(Text(f"\n🔍 Port Scan: {target}\n", style="bold #a78bfa"))
        if self._tool_exists("nmap"):
            out = await self._run(
                f"nmap -sV --top-ports 100 -T4 --open {target}",
                timeout=120
            )
        else:
            self.console.print(Text(
                "  nmap not installed — checking common ports\n",
                style="dim #f59e0b"
            ))
            results = []
            for port in [80, 443, 8080, 8443, 8888, 3000, 5000]:
                r = await self._run(
                    f"curl -s -o /dev/null -w '%{{http_code}}' "
                    f"--max-time 5 https://{target}:{port}",
                    timeout=8
                )
                if r not in ("(no output)", "000", ""):
                    results.append(f"Port {port}: HTTP {r}")
                    self.console.print(Text(f"  Port {port}: {r}", style="#5eead4"))
            out = "\n".join(results) or "(no open ports found)"
        if out != "(no output)":
            REPORTS_DIR.joinpath(f"{target}_ports.txt").write_text(out)
        return out

    async def run_nuclei(self, target: str) -> str:
        self.console.print(Text(f"\n🔍 Vulnerability Scan: {target}\n", style="bold #a78bfa"))
        if not self._tool_exists("nuclei"):
            self.console.print(Text(
                "  nuclei not installed.\n"
                "  Install: go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest\n",
                style="dim #f59e0b"
            ))
            return "(nuclei not installed)"
        out = await self._run(
            f"nuclei -u https://{target} -severity medium,high,critical -silent",
            timeout=180
        )
        if out not in ("(no output)", "(nuclei not installed)"):
            nfile = REPORTS_DIR / f"{target}_nuclei.txt"
            nfile.write_text(out)
            count = len(out.splitlines())
            self.console.print(Text(
                f"\n  ✓ {count} findings → {nfile}\n",
                style="bold #10b981"
            ))
        return out

    async def run_full_recon(self, target: str):
        t0 = time.time()
        self.console.print(Text(
            f"\n{'═'*60}\n  🎯 Bug Bounty Recon: {target}\n{'═'*60}\n",
            style="bold #ef4444"
        ))
        results = {}
        results["subdomains"] = await self.run_subdomains(target)
        results["headers"]    = await self.run_headers(target)
        results["ports"]      = await self.run_ports(target)
        results["nuclei"]     = await self.run_nuclei(target)

        elapsed = int(time.time() - t0)
        self.console.print(Text(f"\n{'═'*60}", style="dim #374151"))
        self.console.print(Text(
            f"  ✓ Recon complete in {elapsed}s\n"
            f"  Reports saved to: {REPORTS_DIR}/\n",
            style="bold #10b981"
        ))
        t = Table(border_style="dim #374151", padding=(0, 2))
        t.add_column("Check", style="#5eead4")
        t.add_column("Result", style="white")
        subs_count = len([
            l for l in results["subdomains"].splitlines() if l.strip()
        ]) if results["subdomains"] != "(no output)" else 0
        t.add_row("Subdomains", f"{subs_count} found")
        t.add_row("Headers", "complete")
        t.add_row("Ports", "complete")
        t.add_row("Nuclei", "complete" if results["nuclei"] != "(nuclei not installed)" else "not installed")
        self.console.print(t)
        self.console.print()

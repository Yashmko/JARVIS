"""
JARVIS v2 — tools/bounty.py

Bug bounty toolkit. Commands:
  bounty recon example.com
  bounty subdomains example.com
  bounty headers example.com
  bounty tech example.com
  bounty nuclei example.com
  bounty ports example.com
  bounty report
  bounty workflow example.com
  bounty scope
  bounty programs
"""
import asyncio
import json
import os
import subprocess
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.panel import Panel


@dataclass
class BountyResult:
    success: bool
    output: str = ""
    error: str = ""
    findings: list = field(default_factory=list)
    target: str = ""
    scan_type: str = ""
    duration_ms: int = 0


# Track current scope
SCOPE_FILE = Path("memory/bounty_scope.json")
REPORTS_DIR = Path("reports")
FINDINGS_FILE = Path("memory/bounty_findings.json")


class BountyToolkit:
    def __init__(self, console: Console, brain=None):
        self.console = console
        self.brain = brain
        REPORTS_DIR.mkdir(exist_ok=True)

    async def execute(self, query: str) -> BountyResult:
        q = query.strip()
        ql = q.lower()

        # Parse command
        parts = ql.replace("bounty ", "").strip().split(" ", 1)
        cmd = parts[0] if parts else ""
        target = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "recon":
            return await self.full_recon(target)
        elif cmd == "subdomains":
            return await self.find_subdomains(target)
        elif cmd == "headers":
            return await self.check_headers(target)
        elif cmd == "tech":
            return await self.detect_tech(target)
        elif cmd == "ports":
            return await self.scan_ports(target)
        elif cmd == "nuclei":
            return await self.run_nuclei(target)
        elif cmd == "report":
            return await self.generate_report(target)
        elif cmd == "workflow":
            return await self.full_workflow(target)
        elif cmd == "scope":
            return self.show_scope()
        elif cmd == "programs":
            return await self.list_programs()
        elif cmd == "install":
            return await self.install_tools()
        else:
            return BountyResult(False, error=(
                "Usage:\n"
                "  bounty recon <domain>      Full recon\n"
                "  bounty subdomains <domain> Find subdomains\n"
                "  bounty headers <domain>    Check security headers\n"
                "  bounty tech <domain>       Detect tech stack\n"
                "  bounty ports <domain>      Port scan\n"
                "  bounty nuclei <domain>     Run nuclei scanner\n"
                "  bounty report              Generate report\n"
                "  bounty workflow <domain>   Full pipeline\n"
                "  bounty scope               Show current scope\n"
                "  bounty programs            List bug bounty programs\n"
                "  bounty install             Install recon tools"
            ))

    # ═════════════════════════════════════════════
    # SCOPE MANAGEMENT
    # ═════════════════════════════════════════════

    def _set_scope(self, target: str):
        scope = {
            "target": target,
            "started": datetime.now().isoformat(),
            "findings": [],
        }
        SCOPE_FILE.parent.mkdir(exist_ok=True)
        SCOPE_FILE.write_text(json.dumps(scope, indent=2))

    def _get_scope(self) -> dict:
        if SCOPE_FILE.exists():
            return json.loads(SCOPE_FILE.read_text())
        return {}

    def _add_finding(self, finding: dict):
        scope = self._get_scope()
        if "findings" not in scope:
            scope["findings"] = []
        scope["findings"].append({
            **finding,
            "ts": datetime.now().isoformat(),
        })
        SCOPE_FILE.write_text(json.dumps(scope, indent=2))

    def show_scope(self) -> BountyResult:
        scope = self._get_scope()
        if not scope:
            return BountyResult(True, output="No active scope. Run: bounty recon <domain>")

        lines = [
            f"Target: {scope.get('target', '?')}",
            f"Started: {scope.get('started', '?')[:19]}",
            f"Findings: {len(scope.get('findings', []))}",
        ]

        for f in scope.get("findings", [])[-10:]:
            sev = f.get("severity", "info")
            lines.append(f"  [{sev.upper()}] {f.get('title', '?')}")

        output = "\n".join(lines)
        self.console.print(Panel(output, title="[bold #ef4444]Bounty Scope[/bold #ef4444]",
                                border_style="dim #374151"))
        return BountyResult(True, output=output)

    # ═════════════════════════════════════════════
    # RECON TOOLS
    # ═════════════════════════════════════════════

    async def _run_tool(self, name: str, cmd: list, target: str) -> str:
        """Run a tool and return output. Handles missing tools gracefully."""
        if not shutil.which(cmd[0]):
            return f"[{name}] Tool '{cmd[0]}' not installed. Run: bounty install"

        self.console.print(Text(f"  ▸ Running {name}...", style="dim #f59e0b"))
        t0 = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )
            ms = int((time.time() - t0) * 1000)
            output = stdout.decode(errors="replace").strip()

            if output:
                lines = output.splitlines()
                self.console.print(Text(f"  ✓ {name}: {len(lines)} results [{ms}ms]",
                                       style="bold #10b981"))
            else:
                self.console.print(Text(f"  ○ {name}: no results [{ms}ms]",
                                       style="dim #6b7280"))
            return output

        except asyncio.TimeoutError:
            return f"[{name}] Timed out after 120s"
        except Exception as e:
            return f"[{name}] Error: {e}"

    async def find_subdomains(self, target: str) -> BountyResult:
        if not target:
            return BountyResult(False, error="Usage: bounty subdomains <domain>")

        self._set_scope(target)
        self.console.print(Text(f"\n  🔍 Subdomain enumeration: {target}\n", style="bold #a78bfa"))

        results = []

        # Try multiple tools
        # 1. subfinder
        out = await self._run_tool("subfinder",
            ["subfinder", "-d", target, "-silent"], target)
        if out and not out.startswith("["):
            results.extend(out.splitlines())

        # 2. curl crt.sh (always available, no install needed)
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", f"https://crt.sh/?q=%.{target}&output=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            data = json.loads(stdout.decode())
            crt_domains = set()
            for entry in data:
                name_value = entry.get("name_value", "")
                for domain in name_value.split("\n"):
                    domain = domain.strip().lstrip("*.")
                    if domain and target in domain:
                        crt_domains.add(domain)
            self.console.print(Text(f"  ✓ crt.sh: {len(crt_domains)} results", style="bold #10b981"))
            results.extend(crt_domains)
        except Exception as e:
            self.console.print(Text(f"  ○ crt.sh: {e}", style="dim #6b7280"))

        # Deduplicate
        unique = sorted(set(results))

        # Display
        if unique:
            t = Table(title=f"Subdomains ({len(unique)})", border_style="dim #374151")
            t.add_column("Subdomain", style="#5eead4")
            for sub in unique[:50]:
                t.add_row(sub)
            if len(unique) > 50:
                t.add_row(f"... +{len(unique)-50} more")
            self.console.print()
            self.console.print(t)

            # Save finding
            self._add_finding({
                "type": "subdomains",
                "severity": "info",
                "title": f"Found {len(unique)} subdomains for {target}",
                "data": unique[:100],
            })

            # Save to file
            outfile = REPORTS_DIR / f"{target}_subdomains.txt"
            outfile.write_text("\n".join(unique))
            self.console.print(Text(f"\n  Saved: {outfile}\n", style="dim #6b7280"))

        return BountyResult(True, output="\n".join(unique), target=target,
                          scan_type="subdomains", findings=[{"count": len(unique)}])

    async def check_headers(self, target: str) -> BountyResult:
        if not target:
            return BountyResult(False, error="Usage: bounty headers <domain>")

        self.console.print(Text(f"\n  🔍 Security headers: {target}\n", style="bold #a78bfa"))

        url = target if target.startswith("http") else f"https://{target}"

        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-I", "-L", "--max-time", "10", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            headers_raw = stdout.decode(errors="replace")

            # Parse headers
            headers = {}
            for line in headers_raw.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    headers[key.strip().lower()] = val.strip()

            # Check security headers
            security_headers = {
                "strict-transport-security": ("HSTS", "critical"),
                "content-security-policy": ("CSP", "high"),
                "x-frame-options": ("X-Frame-Options", "medium"),
                "x-content-type-options": ("X-Content-Type-Options", "medium"),
                "x-xss-protection": ("X-XSS-Protection", "low"),
                "referrer-policy": ("Referrer-Policy", "low"),
                "permissions-policy": ("Permissions-Policy", "low"),
                "x-permitted-cross-domain-policies": ("Cross-Domain", "low"),
            }

            t = Table(title=f"Security Headers: {target}", border_style="dim #374151")
            t.add_column("Header", style="cyan")
            t.add_column("Status", justify="center")
            t.add_column("Severity", justify="center")
            t.add_column("Value")

            missing = []
            for header_key, (name, severity) in security_headers.items():
                value = headers.get(header_key, "")
                if value:
                    t.add_row(name, "[green]✓[/green]", severity, value[:60])
                else:
                    t.add_row(name, "[red]✗ MISSING[/red]", f"[red]{severity}[/red]", "")
                    missing.append({"header": name, "severity": severity})

            self.console.print(t)
            self.console.print()

            # Server header (info leak)
            server = headers.get("server", "")
            if server:
                self.console.print(f"  [yellow]⚠ Server header exposed:[/yellow] {server}")
                missing.append({"header": "Server (info leak)", "severity": "info", "value": server})

            # Save findings
            for m in missing:
                self._add_finding({
                    "type": "missing_header",
                    "severity": m["severity"],
                    "title": f"Missing: {m['header']}",
                    "target": target,
                })

            return BountyResult(True, output=headers_raw, target=target,
                              scan_type="headers", findings=missing)

        except Exception as e:
            return BountyResult(False, error=str(e))

    async def detect_tech(self, target: str) -> BountyResult:
        if not target:
            return BountyResult(False, error="Usage: bounty tech <domain>")

        self.console.print(Text(f"\n  🔍 Tech detection: {target}\n", style="bold #a78bfa"))

        url = target if target.startswith("http") else f"https://{target}"

        # Use curl to get page + headers
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", "--max-time", "10",
                "-H", "User-Agent: Mozilla/5.0", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            body = stdout.decode(errors="replace").lower()

            # Also get headers
            proc2 = await asyncio.create_subprocess_exec(
                "curl", "-s", "-I", "-L", "--max-time", "10", url,
                stdout=asyncio.subprocess.PIPE,
            )
            stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=15)
            headers = stdout2.decode(errors="replace").lower()

            # Tech signatures
            techs = []
            checks = [
                ("React", ["react", "reactdom", "_next/static", "__next"]),
                ("Next.js", ["_next/", "__next", "next.js"]),
                ("Vue.js", ["vue.js", "vuejs", "__vue__"]),
                ("Angular", ["ng-version", "angular", "ng-app"]),
                ("jQuery", ["jquery", "jquery.min.js"]),
                ("WordPress", ["wp-content", "wp-includes", "wordpress"]),
                ("Nginx", ["nginx"]),
                ("Apache", ["apache"]),
                ("Cloudflare", ["cloudflare", "cf-ray"]),
                ("AWS", ["amazonaws", "aws", "x-amz"]),
                ("Node.js", ["x-powered-by: express", "node.js"]),
                ("PHP", ["x-powered-by: php", ".php"]),
                ("Python/Django", ["django", "csrfmiddlewaretoken"]),
                ("Python/Flask", ["werkzeug", "flask"]),
                ("Ruby/Rails", ["x-powered-by: phusion", "rails", "csrf-token"]),
                ("Bootstrap", ["bootstrap"]),
                ("Tailwind", ["tailwind"]),
                ("Google Analytics", ["google-analytics", "gtag", "ga.js"]),
                ("Google Tag Manager", ["googletagmanager"]),
                ("Stripe", ["stripe.js", "stripe.com"]),
                ("Sentry", ["sentry", "sentry.io"]),
                ("Webpack", ["webpack", "webpackjsonp"]),
                ("Docker", ["docker"]),
                ("GraphQL", ["graphql", "/graphql"]),
            ]

            combined = body + "\n" + headers
            for tech, signatures in checks:
                if any(sig in combined for sig in signatures):
                    techs.append(tech)

            t = Table(title=f"Tech Stack: {target}", border_style="dim #374151")
            t.add_column("Technology", style="#5eead4")
            for tech in techs:
                t.add_row(tech)

            self.console.print(t)
            self.console.print()

            self._add_finding({
                "type": "tech_stack",
                "severity": "info",
                "title": f"Detected {len(techs)} technologies",
                "data": techs,
                "target": target,
            })

            return BountyResult(True, output="\n".join(techs), target=target,
                              scan_type="tech")

        except Exception as e:
            return BountyResult(False, error=str(e))

    async def scan_ports(self, target: str) -> BountyResult:
        if not target:
            return BountyResult(False, error="Usage: bounty ports <domain>")

        self.console.print(Text(f"\n  🔍 Port scan: {target}\n", style="bold #a78bfa"))

        # Use nmap if available, otherwise bash /dev/tcp
        if shutil.which("nmap"):
            out = await self._run_tool("nmap",
                ["nmap", "-sT", "--top-ports", "100", "-T4", "--open", target], target)
        else:
            # Fallback: bash port scan (common ports)
            self.console.print(Text("  ▸ Using built-in port scanner (install nmap for better results)",
                                   style="dim #f59e0b"))
            ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995,
                    1433, 1521, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 8888, 9090, 27017]
            open_ports = []

            for port in ports:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "bash", "-c", f"echo >/dev/tcp/{target}/{port}",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await asyncio.wait_for(proc.communicate(), timeout=2)
                    if proc.returncode == 0:
                        open_ports.append(port)
                        self.console.print(f"  [green]✓ Port {port} OPEN[/green]")
                except Exception:
                    pass

            out = "\n".join(f"Port {p}: OPEN" for p in open_ports)

            if open_ports:
                self._add_finding({
                    "type": "open_ports",
                    "severity": "info",
                    "title": f"Found {len(open_ports)} open ports",
                    "data": open_ports,
                    "target": target,
                })

        if out:
            self.console.print(Text(f"\n{out}\n", style="#9ca3af"))

        return BountyResult(True, output=out or "No open ports found", target=target,
                          scan_type="ports")

    async def run_nuclei(self, target: str) -> BountyResult:
        if not target:
            return BountyResult(False, error="Usage: bounty nuclei <domain>")

        if not shutil.which("nuclei"):
            return BountyResult(False, error=(
                "nuclei not installed.\n"
                "  Install: go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest\n"
                "  Or: bounty install"
            ))

        self.console.print(Text(f"\n  🔍 Nuclei scan: {target}\n", style="bold #a78bfa"))

        url = target if target.startswith("http") else f"https://{target}"
        out = await self._run_tool("nuclei",
            ["nuclei", "-u", url, "-severity", "medium,high,critical",
             "-silent", "-no-color"], target)

        if out:
            findings = []
            for line in out.splitlines():
                if line.strip():
                    findings.append(line)
                    # Try to parse severity
                    sev = "medium"
                    if "critical" in line.lower():
                        sev = "critical"
                    elif "high" in line.lower():
                        sev = "high"

                    self._add_finding({
                        "type": "nuclei",
                        "severity": sev,
                        "title": line[:200],
                        "target": target,
                    })

            self.console.print(Text(f"\n  Found {len(findings)} potential vulnerabilities\n",
                                   style="bold #ef4444"))

        return BountyResult(True, output=out or "No vulnerabilities found", target=target,
                          scan_type="nuclei")

    # ═════════════════════════════════════════════
    # FULL RECON + WORKFLOW
    # ═════════════════════════════════════════════

    async def full_recon(self, target: str) -> BountyResult:
        if not target:
            return BountyResult(False, error="Usage: bounty recon <domain>")

        self.console.print(Text(f"\n  🎯 Full Recon: {target}", style="bold #ef4444"))
        self.console.print(Text(f"  {'═' * 50}\n", style="dim #374151"))
        self._set_scope(target)

        t0 = time.time()

        # Run all scans
        await self.find_subdomains(target)
        await self.check_headers(target)
        await self.detect_tech(target)
        await self.scan_ports(target)

        ms = int((time.time() - t0) * 1000)
        scope = self._get_scope()
        findings_count = len(scope.get("findings", []))

        self.console.print(Text(f"\n  {'═' * 50}", style="dim #374151"))
        self.console.print(Text(f"  ✓ Recon complete: {findings_count} findings in {ms/1000:.1f}s",
                               style="bold #10b981"))
        self.console.print(Text(f"  Run 'bounty report' to generate full report\n",
                               style="dim #6b7280"))

        return BountyResult(True, output=f"{findings_count} findings", target=target,
                          scan_type="recon", duration_ms=ms)

    async def full_workflow(self, target: str) -> BountyResult:
        """Full pipeline: recon → nuclei → AI analysis → report"""
        if not target:
            return BountyResult(False, error="Usage: bounty workflow <domain>")

        # Run recon
        await self.full_recon(target)

        # Run nuclei if available
        if shutil.which("nuclei"):
            await self.run_nuclei(target)

        # AI analysis
        if self.brain:
            scope = self._get_scope()
            findings_text = json.dumps(scope.get("findings", [])[:20], indent=2)

            self.console.print(Text("\n  🧠 AI analyzing findings...\n", style="bold #a78bfa"))

            prompt = [{
                "role": "user",
                "content": (
                    f"Analyze these bug bounty recon findings for {target}.\n"
                    f"Findings:\n{findings_text}\n\n"
                    f"For each finding:\n"
                    f"1. Rate severity (critical/high/medium/low/info)\n"
                    f"2. Explain the risk\n"
                    f"3. Suggest exploitation path\n"
                    f"4. Recommend fix\n"
                    f"5. Estimate bounty value if applicable\n"
                    f"Format as a security report."
                )
            }]

            analysis = ""
            async for chunk in self.brain.stream(prompt):
                analysis += chunk
                self.console.print(chunk, end="")
            self.console.print("\n")

        # Generate report
        await self.generate_report(target)

        return BountyResult(True, output="Workflow complete", target=target)

    # ═════════════════════════════════════════════
    # REPORT GENERATION
    # ═════════════════════════════════════════════

    async def generate_report(self, target: str = "") -> BountyResult:
        scope = self._get_scope()
        if not scope:
            return BountyResult(False, error="No recon data. Run: bounty recon <domain>")

        target = target or scope.get("target", "unknown")
        findings = scope.get("findings", [])
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Count by severity
        by_sev = {}
        for f in findings:
            s = f.get("severity", "info")
            by_sev[s] = by_sev.get(s, 0) + 1

        # Build markdown report
        report = f"""# Bug Bounty Report: {target}
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Scanner:** JARVIS v2 Bug Bounty Toolkit

## Summary
- **Target:** {target}
- **Total Findings:** {len(findings)}
- **Critical:** {by_sev.get('critical', 0)}
- **High:** {by_sev.get('high', 0)}
- **Medium:** {by_sev.get('medium', 0)}
- **Low:** {by_sev.get('low', 0)}
- **Info:** {by_sev.get('info', 0)}

## Findings

"""
        for i, f in enumerate(findings, 1):
            sev = f.get("severity", "info").upper()
            title = f.get("title", "?")
            ftype = f.get("type", "?")
            report += f"### {i}. [{sev}] {title}\n"
            report += f"- **Type:** {ftype}\n"
            report += f"- **Timestamp:** {f.get('ts', '?')[:19]}\n"
            if f.get("data"):
                data = f["data"]
                if isinstance(data, list):
                    report += f"- **Data:** {', '.join(str(d) for d in data[:10])}\n"
                else:
                    report += f"- **Data:** {data}\n"
            report += "\n"

        report += """## Recommendations

1. Fix all critical and high severity findings immediately
2. Implement missing security headers
3. Review exposed services and close unnecessary ports
4. Update all software to latest versions
5. Conduct regular security assessments

---
*Generated by JARVIS v2 Bug Bounty Toolkit*
"""

        # Save report
        outfile = REPORTS_DIR / f"bounty_report_{target}_{ts}.md"
        outfile.write_text(report)

        # Also save as JSON
        json_file = REPORTS_DIR / f"bounty_report_{target}_{ts}.json"
        json_file.write_text(json.dumps({
            "target": target,
            "date": datetime.now().isoformat(),
            "summary": by_sev,
            "findings": findings,
        }, indent=2))

        self.console.print(Panel(
            f"Report generated:\n"
            f"  Markdown: {outfile}\n"
            f"  JSON:     {json_file}\n"
            f"  Findings: {len(findings)} total\n"
            f"  Critical: {by_sev.get('critical', 0)} | "
            f"High: {by_sev.get('high', 0)} | "
            f"Medium: {by_sev.get('medium', 0)}",
            title="[bold #10b981]Report Generated[/bold #10b981]",
            border_style="dim #374151",
        ))

        return BountyResult(True, output=f"Report saved: {outfile}", target=target)

    # ═════════════════════════════════════════════
    # TOOL INSTALLATION
    # ═════════════════════════════════════════════

    async def install_tools(self) -> BountyResult:
        self.console.print(Text("\n  Installing bug bounty tools...\n", style="bold #a78bfa"))

        tools = [
            ("nmap", "sudo pacman -S nmap --noconfirm"),
            ("curl", "sudo pacman -S curl --noconfirm"),
            ("whois", "sudo pacman -S whois --noconfirm"),
        ]

        for name, cmd in tools:
            if shutil.which(name):
                self.console.print(f"  [green]✓[/green] {name} already installed")
            else:
                self.console.print(f"  [yellow]▸[/yellow] Installing {name}...")
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

        # Go tools (optional)
        go_tools = [
            ("subfinder", "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"),
            ("httpx", "go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest"),
            ("nuclei", "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"),
        ]

        if shutil.which("go"):
            for name, cmd in go_tools:
                if shutil.which(name):
                    self.console.print(f"  [green]✓[/green] {name} already installed")
                else:
                    self.console.print(f"  [yellow]▸[/yellow] Installing {name}...")
                    proc = await asyncio.create_subprocess_shell(
                        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await proc.communicate()
        else:
            self.console.print("\n  [dim]Go not installed. For nuclei/subfinder/httpx:")
            self.console.print("  sudo pacman -S go")
            self.console.print("  Then: bounty install[/dim]")

        self.console.print()
        return BountyResult(True, output="Tools installed")

    async def list_programs(self) -> BountyResult:
        """Show popular bug bounty programs."""
        programs = [
            ("HackerOne", "https://hackerone.com/bug-bounty-programs", "$50-$100k+"),
            ("Bugcrowd", "https://bugcrowd.com/programs", "$50-$50k+"),
            ("Intigriti", "https://intigriti.com/programs", "€50-€50k+"),
            ("YesWeHack", "https://yeswehack.com/programs", "€50-€30k+"),
            ("Google VRP", "https://bughunters.google.com", "$100-$31k"),
            ("GitHub", "https://bounty.github.com", "$617-$30k"),
            ("Meta", "https://facebook.com/whitehat", "$500-$50k+"),
            ("Microsoft", "https://msrc.microsoft.com/bounty", "$500-$100k+"),
            ("Apple", "https://security.apple.com/bounty", "$5k-$1M"),
        ]

        t = Table(title="Bug Bounty Programs", border_style="dim #374151")
        t.add_column("Program", style="#5eead4")
        t.add_column("URL", style="dim")
        t.add_column("Bounty Range", style="#f59e0b")
        for name, url, bounty in programs:
            t.add_row(name, url, bounty)

        self.console.print()
        self.console.print(t)
        self.console.print()
        return BountyResult(True, output="Programs listed")


# ═════════════════════════════════════════════
# KEYWORD DETECTOR
# ═════════════════════════════════════════════

BOUNTY_PREFIXES = (
    "bounty ", "bounty:",
)

def is_bounty_command(query: str) -> bool:
    ql = query.lower().strip()
    return any(ql.startswith(p) for p in BOUNTY_PREFIXES)

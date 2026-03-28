"""
JARVIS v2 — tools/browser_auto.py

Lightweight browser automation — no Selenium, no Playwright.
Uses curl + Python for scraping. Minimal RAM.

Commands:
  scrape <url>              Get page content
  scrape links <url>        Extract all links
  scrape emails <url>       Extract emails
  scrape title <url>        Get page title
  screenshot url <url>      Take screenshot (if cutycapt installed)
  monitor <url>             Check if site is up
  download <url> <file>     Download a file
"""
import asyncio
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.text import Text
from rich.table import Table


@dataclass
class BrowserResult:
    success: bool
    output: str = ""
    error: str = ""


class BrowserAutomation:
    def __init__(self, console: Console):
        self.console = console

    async def execute(self, query: str) -> BrowserResult:
        q = query.strip()
        ql = q.lower()

        if ql.startswith("scrape links "):
            return await self.scrape_links(q.split(" ", 2)[2].strip())

        if ql.startswith("scrape emails "):
            return await self.scrape_emails(q.split(" ", 2)[2].strip())

        if ql.startswith("scrape title "):
            return await self.scrape_title(q.split(" ", 2)[2].strip())

        if ql.startswith("scrape "):
            return await self.scrape_page(q.split(" ", 1)[1].strip())

        if ql.startswith("monitor "):
            return await self.monitor_url(q.split(" ", 1)[1].strip())

        if ql.startswith("download "):
            parts = q.split(" ", 2)
            if len(parts) >= 3:
                return await self.download(parts[1], parts[2])
            return BrowserResult(False, error="Usage: download <url> <filename>")

        return BrowserResult(False, error=(
            "Usage:\n"
            "  scrape <url>        Get page content\n"
            "  scrape links <url>  Extract links\n"
            "  scrape emails <url> Extract emails\n"
            "  scrape title <url>  Get page title\n"
            "  monitor <url>       Check if up\n"
            "  download <url> <f>  Download file"
        ))

    async def _fetch(self, url: str, follow: bool = True) -> tuple[str, str]:
        """Fetch URL with curl. Returns (body, headers)."""
        if not url.startswith("http"):
            url = "https://" + url

        cmd = ["curl", "-s", "-L" if follow else "", "--max-time", "15",
               "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
               "-D", "-", url]
        cmd = [c for c in cmd if c]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
            output = stdout.decode(errors="replace")

            # Split headers and body
            parts = output.split("\r\n\r\n", 1)
            if len(parts) == 2:
                return parts[1], parts[0]
            return output, ""
        except asyncio.TimeoutError:
            return "", "Timeout"
        except Exception as e:
            return "", str(e)

    async def scrape_page(self, url: str) -> BrowserResult:
        self.console.print(Text(f"\n  🌐 Scraping: {url}\n", style="bold #a78bfa"))

        body, headers = await self._fetch(url)
        if not body:
            return BrowserResult(False, error=f"Could not fetch {url}")

        # Strip HTML tags for readable text
        text = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Truncate
        if len(text) > 3000:
            text = text[:3000] + "\n\n... (truncated)"

        self.console.print(text[:2000])
        self.console.print()

        return BrowserResult(True, output=text)

    async def scrape_links(self, url: str) -> BrowserResult:
        self.console.print(Text(f"\n  🔗 Extracting links: {url}\n", style="bold #a78bfa"))

        body, _ = await self._fetch(url)
        if not body:
            return BrowserResult(False, error=f"Could not fetch {url}")

        # Extract links
        links = re.findall(r'href=["\']([^"\']+)["\']', body)
        links = sorted(set(links))

        # Filter
        external = [l for l in links if l.startswith("http")]
        internal = [l for l in links if l.startswith("/")]

        t = Table(title=f"Links ({len(links)})", border_style="dim #374151")
        t.add_column("Type", style="dim")
        t.add_column("URL", style="#5eead4")

        for l in external[:30]:
            t.add_row("ext", l[:80])
        for l in internal[:20]:
            t.add_row("int", l[:80])

        if len(links) > 50:
            t.add_row("...", f"+{len(links)-50} more")

        self.console.print(t)
        self.console.print()

        return BrowserResult(True, output="\n".join(links[:100]))

    async def scrape_emails(self, url: str) -> BrowserResult:
        self.console.print(Text(f"\n  📧 Extracting emails: {url}\n", style="bold #a78bfa"))

        body, _ = await self._fetch(url)
        if not body:
            return BrowserResult(False, error=f"Could not fetch {url}")

        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', body)
        emails = sorted(set(emails))

        if emails:
            for e in emails[:20]:
                self.console.print(f"  [#5eead4]{e}[/#5eead4]")
        else:
            self.console.print("  [dim]No emails found.[/dim]")
        self.console.print()

        return BrowserResult(True, output="\n".join(emails))

    async def scrape_title(self, url: str) -> BrowserResult:
        body, _ = await self._fetch(url)
        if not body:
            return BrowserResult(False, error=f"Could not fetch {url}")

        match = re.search(r'<title[^>]*>(.*?)</title>', body, re.IGNORECASE | re.DOTALL)
        title = match.group(1).strip() if match else "(no title)"

        self.console.print(f"  [bold]{title}[/bold]\n")
        return BrowserResult(True, output=title)

    async def monitor_url(self, url: str) -> BrowserResult:
        if not url.startswith("http"):
            url = "https://" + url

        self.console.print(Text(f"  Checking: {url}...", style="dim"))

        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code} %{time_total}",
                "--max-time", "10", "-L", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            parts = stdout.decode().strip().split()
            code = parts[0] if parts else "?"
            time_s = parts[1] if len(parts) > 1 else "?"

            if code.startswith("2"):
                self.console.print(f"  [bold #10b981]✓ UP[/bold #10b981]  Status: {code}  Time: {time_s}s\n")
            elif code.startswith("3"):
                self.console.print(f"  [bold #f59e0b]↪ REDIRECT[/bold #f59e0b]  Status: {code}  Time: {time_s}s\n")
            else:
                self.console.print(f"  [bold #ef4444]✗ DOWN[/bold #ef4444]  Status: {code}  Time: {time_s}s\n")

            return BrowserResult(True, output=f"Status: {code}, Time: {time_s}s")
        except Exception as e:
            self.console.print(f"  [bold #ef4444]✗ DOWN[/bold #ef4444]  Error: {e}\n")
            return BrowserResult(False, error=str(e))

    async def download(self, url: str, filename: str) -> BrowserResult:
        if not url.startswith("http"):
            url = "https://" + url

        self.console.print(Text(f"  Downloading: {url}...", style="dim"))

        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", "--max-time", "60", "-o", filename, url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=65)

            if Path(filename).exists():
                size = Path(filename).stat().st_size
                for unit in ("B", "KB", "MB"):
                    if size < 1024:
                        size_str = f"{size:.0f}{unit}"
                        break
                    size /= 1024
                else:
                    size_str = f"{size:.0f}GB"
                self.console.print(f"  [bold #10b981]✓ Downloaded:[/bold #10b981] {filename} ({size_str})\n")
                return BrowserResult(True, output=f"Downloaded: {filename}")
            else:
                return BrowserResult(False, error="Download failed")
        except Exception as e:
            return BrowserResult(False, error=str(e))


BROWSER_PREFIXES = ("scrape ", "monitor ", "download ")

def is_browser_command(query: str) -> bool:
    ql = query.lower().strip()
    return any(ql.startswith(p) for p in BROWSER_PREFIXES)

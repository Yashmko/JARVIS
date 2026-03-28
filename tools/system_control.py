"""
JARVIS v2 — tools/system_control.py
Full OS-level control for Arch Linux + i3.
"""
import asyncio
import os
import platform
import shutil
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.text import Text
from rich.panel import Panel


@dataclass
class SysResult:
    success: bool
    output: str = ""
    error: str = ""

    def __str__(self):
        return self.output if self.success else f"[ERROR] {self.error}"


DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -r /", "mkfs", "dd if=/dev/zero",
    "> /dev/sda", ":(){ :|:& };:", "chmod -R 777 /",
    "shutdown", "reboot", "poweroff", "halt",
]

BLOCKED_PATTERNS = [
    ":(){ :|:& };:", "> /dev/sda", "dd if=/dev/zero of=/dev/",
]

APP_MAP = {
    "chrome": "google-chrome-stable",
    "chromium": "chromium",
    "firefox": "firefox",
    "code": "code",
    "vscode": "code",
    "cursor": "cursor",
    "terminal": "kitty",
    "kitty": "kitty",
    "files": "thunar",
    "thunar": "thunar",
    "nautilus": "nautilus",
    "slack": "slack",
    "discord": "discord",
    "spotify": "spotify",
    "telegram": "telegram-desktop",
    "obs": "obs",
    "gimp": "gimp",
    "vlc": "vlc",
    "mpv": "mpv",
    "htop": "htop",
    "btop": "btop",
    "ranger": "ranger",
    "vim": "vim",
    "nvim": "nvim",
    "nano": "nano",
    "pcmanfm": "pcmanfm",
}


class SystemController:
    def __init__(self, console: Console):
        self.console = console

    async def execute(self, query: str) -> SysResult:
        q = query.strip()
        ql = q.lower()

        # Blocked
        if any(p.lower() in q.lower() for p in BLOCKED_PATTERNS):
            return SysResult(False, error="Blocked: dangerous command.")

        # Dangerous — confirm
        if any(p.lower() in q.lower() for p in DANGEROUS_PATTERNS):
            if not await self._confirm(q):
                return SysResult(False, error="Cancelled by user.")

        # ── ROUTE ────────────────────────────────
        if ql.startswith(("open ", "launch ", "start ")):
            app = q.split(" ", 1)[1].strip()
            return await self.open_app(app)

        if ql.startswith("run:") or (ql.startswith("run ") and not ql.startswith("run:")):
            cmd = q.split(":", 1)[1].strip() if ":" in q else q.split(" ", 1)[1].strip()
            return await self.run_command(cmd)

        if ql.startswith(("kill ", "stop ", "close ")):
            name = q.split(" ", 1)[1].strip()
            return self.kill_process(name)

        if ql.startswith("volume"):
            parts = ql.split()
            level = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            return self.set_volume(level)

        if ql == "mute":
            return self.mute()
        if ql == "unmute":
            return self.unmute()

        if ql.startswith("brightness"):
            parts = ql.split()
            level = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 70
            return self.set_brightness(level)

        if ql in ("screenshot", "screen", "capture"):
            return self.take_screenshot()

        if ql.startswith("notify "):
            msg = q.split(" ", 1)[1].strip().strip("\"'")
            return self.send_notification(msg)

        if ql.startswith(("url ", "browse ")):
            url = q.split(" ", 1)[1].strip()
            return self.open_url(url)

        if ql in ("sysinfo", "system info", "cpu", "ram", "disk", "memory"):
            return self.system_info()

        if ql.startswith(("list process", "ps", "processes")):
            return self.list_processes()

        if ql in ("sleep", "suspend"):
            return self.sleep_system()

        if ql in ("shutdown", "power off"):
            return self.shutdown()

        if ql in ("restart", "reboot"):
            return self.restart()

        if "schedule" in ql:
            return await self._schedule(q)

        return SysResult(False, error=f"Unknown system command: '{q}'")

    # ── CONFIRM ──────────────────────────────────
    async def _confirm(self, cmd: str) -> bool:
        self.console.print(
            Text(f"\n  ⚠ DANGEROUS: {cmd}\n  Type 'yes' to proceed: ",
                 style="bold #ef4444"), end=""
        )
        try:
            resp = await asyncio.get_event_loop().run_in_executor(None, input)
            return resp.strip().lower() in ("yes", "y")
        except Exception:
            return False

    # ── OPEN APP ─────────────────────────────────
    async def open_app(self, name: str) -> SysResult:
        resolved = APP_MAP.get(name.lower(), name.lower().replace(" ", "-"))
        if shutil.which(resolved):
            subprocess.Popen(
                [resolved],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return SysResult(True, output=f"Launched {resolved}")

        # Try xdg-open
        try:
            subprocess.Popen(["xdg-open", name])
            return SysResult(True, output=f"Opened {name} via xdg-open")
        except Exception as e:
            return SysResult(False, error=f"App not found: '{name}'")

    # ── RUN COMMAND ──────────────────────────────
    async def run_command(self, cmd: str, timeout: int = 60) -> SysResult:
        self.console.print(Text(f"\n  $ {cmd}\n", style="bold #5eead4"))
        start = time.time()
        output_lines = []

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(Path.cwd()),
            )

            async def read_stream():
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode(errors="replace").rstrip()
                    output_lines.append(decoded)
                    self.console.print(Text(f"  {decoded}", style="#9ca3af"))

            await asyncio.wait_for(read_stream(), timeout=timeout)
            await proc.wait()

            ms = int((time.time() - start) * 1000)
            full_output = "\n".join(output_lines)

            if proc.returncode == 0:
                self.console.print(Text(f"\n  ✓ Done [{ms}ms]\n", style="dim #10b981"))
                return SysResult(True, output=full_output)
            else:
                self.console.print(Text(f"\n  ✗ Exit {proc.returncode} [{ms}ms]\n", style="dim #ef4444"))
                return SysResult(False, output=full_output, error=f"Exit code {proc.returncode}")

        except asyncio.TimeoutError:
            return SysResult(False, error=f"Timed out after {timeout}s")
        except Exception as e:
            return SysResult(False, error=str(e))

    # ── KILL ─────────────────────────────────────
    def kill_process(self, name: str) -> SysResult:
        r = subprocess.run(["pkill", "-f", name], capture_output=True, text=True)
        if r.returncode == 0:
            return SysResult(True, output=f"Killed: {name}")
        return SysResult(False, error=f"Could not kill '{name}'")

    # ── VOLUME ───────────────────────────────────
    def set_volume(self, level: Optional[int] = None) -> SysResult:
        if level is None:
            return SysResult(False, error="Specify 0-100, e.g. 'volume 70'")
        level = max(0, min(100, level))
        try:
            # Try pamixer first (common on Arch)
            if shutil.which("pamixer"):
                subprocess.run(["pamixer", "--set-volume", str(level)], check=True)
            elif shutil.which("amixer"):
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"],
                             check=True, capture_output=True)
            elif shutil.which("wpctl"):
                subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{level/100}"],
                             check=True, capture_output=True)
            else:
                return SysResult(False, error="No volume tool found (install pamixer or amixer)")
            return SysResult(True, output=f"Volume set to {level}%")
        except Exception as e:
            return SysResult(False, error=str(e))

    def mute(self) -> SysResult:
        try:
            if shutil.which("pamixer"):
                subprocess.run(["pamixer", "--mute"])
            elif shutil.which("amixer"):
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "mute"],
                             capture_output=True)
            return SysResult(True, output="Muted")
        except Exception as e:
            return SysResult(False, error=str(e))

    def unmute(self) -> SysResult:
        try:
            if shutil.which("pamixer"):
                subprocess.run(["pamixer", "--unmute"])
            elif shutil.which("amixer"):
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "unmute"],
                             capture_output=True)
            return SysResult(True, output="Unmuted")
        except Exception as e:
            return SysResult(False, error=str(e))

    # ── BRIGHTNESS ───────────────────────────────
    def set_brightness(self, level: int) -> SysResult:
        level = max(0, min(100, level))
        try:
            if shutil.which("brightnessctl"):
                subprocess.run(["brightnessctl", "set", f"{level}%"],
                             check=True, capture_output=True)
            elif shutil.which("xrandr"):
                brightness_f = round(level / 100, 2)
                subprocess.run(["xrandr", "--output", "eDP-1", "--brightness",
                              str(brightness_f)], capture_output=True)
            else:
                return SysResult(False, error="No brightness tool found")
            return SysResult(True, output=f"Brightness set to {level}%")
        except Exception as e:
            return SysResult(False, error=str(e))

    # ── SCREENSHOT ───────────────────────────────
    def take_screenshot(self) -> SysResult:
        ts = int(time.time())
        path = Path.home() / f"jarvis_screenshot_{ts}.png"
        try:
            if shutil.which("scrot"):
                subprocess.run(["scrot", str(path)], check=True)
            elif shutil.which("maim"):
                subprocess.run(["maim", str(path)], check=True)
            elif shutil.which("import"):
                subprocess.run(["import", "-window", "root", str(path)], check=True)
            elif shutil.which("grim"):
                subprocess.run(["grim", str(path)], check=True)
            else:
                return SysResult(False, error="No screenshot tool found (install scrot or maim)")
            return SysResult(True, output=f"Screenshot saved: {path}")
        except Exception as e:
            return SysResult(False, error=str(e))

    # ── NOTIFICATION ─────────────────────────────
    def send_notification(self, message: str, title: str = "Jarvis") -> SysResult:
        try:
            if shutil.which("notify-send"):
                subprocess.run(["notify-send", title, message])
            elif shutil.which("dunstify"):
                subprocess.run(["dunstify", title, message])
            else:
                return SysResult(False, error="No notification tool (install dunst or libnotify)")
            return SysResult(True, output=f"Notification sent: {message}")
        except Exception as e:
            return SysResult(False, error=str(e))

    # ── BROWSER ──────────────────────────────────
    def open_url(self, url: str) -> SysResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            webbrowser.open(url)
            return SysResult(True, output=f"Opened: {url}")
        except Exception as e:
            return SysResult(False, error=str(e))

    # ── SYSINFO ──────────────────────────────────
    def system_info(self) -> SysResult:
        lines = []
        try:
            # RAM
            r = subprocess.run(["free", "-h"], capture_output=True, text=True)
            lines.append("RAM:\n" + r.stdout.strip())

            # Disk
            r2 = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
            lines.append("\nDisk:\n" + r2.stdout.strip())

            # CPU
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        lines.append(f"\nCPU: {line.split(':')[1].strip()}")
                        break

            # Uptime
            r3 = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
            lines.append(f"Uptime: {r3.stdout.strip()}")

            # Kernel
            lines.append(f"Kernel: {platform.release()}")
            lines.append(f"Python: {platform.python_version()}")

        except Exception as e:
            lines.append(f"Error: {e}")

        output = "\n".join(lines)
        self.console.print(Panel(output, title="[bold #5eead4]System Info[/bold #5eead4]",
                                border_style="dim #374151"))
        return SysResult(True, output=output)

    # ── PROCESS LIST ─────────────────────────────
    def list_processes(self) -> SysResult:
        r = subprocess.run(
            ["ps", "aux", "--sort=-%cpu"],
            capture_output=True, text=True
        )
        output = "\n".join(r.stdout.splitlines()[:16])
        self.console.print(Text(output, style="dim #9ca3af"))
        return SysResult(True, output=output)

    # ── POWER ────────────────────────────────────
    def sleep_system(self) -> SysResult:
        try:
            subprocess.Popen(["systemctl", "suspend"])
            return SysResult(True, output="Sleeping...")
        except Exception as e:
            return SysResult(False, error=str(e))

    def shutdown(self) -> SysResult:
        try:
            subprocess.Popen(["systemctl", "poweroff"])
            return SysResult(True, output="Shutting down...")
        except Exception as e:
            return SysResult(False, error=str(e))

    def restart(self) -> SysResult:
        try:
            subprocess.Popen(["systemctl", "reboot"])
            return SysResult(True, output="Restarting...")
        except Exception as e:
            return SysResult(False, error=str(e))

    # ── SCHEDULER ────────────────────────────────
    async def _schedule(self, query: str) -> SysResult:
        import re
        m = re.search(r'schedule\s+"(.+?)"\s+in\s+(\d+)\s+(second|minute|hour)s?',
                      query, re.IGNORECASE)
        if not m:
            return SysResult(False, error='Format: schedule "command" in N seconds/minutes/hours')

        cmd = m.group(1)
        amount = int(m.group(2))
        unit = m.group(3).lower()
        seconds = amount * {"second": 1, "minute": 60, "hour": 3600}[unit]

        self.console.print(Text(f"\n  ⏱ Scheduled: '{cmd}' in {amount} {unit}(s)\n",
                               style="dim #f59e0b"))

        async def _run_later():
            await asyncio.sleep(seconds)
            await self.run_command(cmd)

        asyncio.create_task(_run_later())
        return SysResult(True, output=f"Scheduled '{cmd}' in {seconds}s")


# ── KEYWORD DETECTOR ─────────────────────────────
SYS_PREFIXES = (
    "open ", "launch ", "start ", "run:", "run ",
    "kill ", "stop ", "close ", "volume", "mute", "unmute",
    "brightness", "screenshot", "screen capture",
    "notify ", "notification ", "url ", "browse ",
    "sysinfo", "cpu", "ram", "disk", "memory",
    "list process", "ps ", "sleep", "shutdown",
    "restart", "reboot", "schedule ",
)


def is_sys_command(query: str) -> bool:
    ql = query.lower().strip()
    return any(ql.startswith(p) for p in SYS_PREFIXES)

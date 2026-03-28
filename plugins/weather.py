"""Weather plugin — type 'weather <city>'"""
import subprocess

COMMANDS = ["weather"]
DESCRIPTION = "Get weather for a city (uses wttr.in)"


async def run(query, console, brain=None, memory=None):
    parts = query.strip().split(" ", 1)
    city = parts[1].strip() if len(parts) > 1 else ""

    if not city:
        console.print("  [dim]Usage: weather <city>[/dim]\n")
        return

    try:
        r = subprocess.run(
            ["curl", "-s", f"https://wttr.in/{city}?format=3"],
            capture_output=True, text=True, timeout=10
        )
        console.print(f"  {r.stdout.strip()}\n")
        return r.stdout.strip()
    except Exception as e:
        console.print(f"  [red]Error: {e}[/red]\n")

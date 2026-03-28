"""Timer plugin — type 'timer 5' for 5 second timer"""
import asyncio

COMMANDS = ["timer", "countdown"]
DESCRIPTION = "Set a countdown timer (seconds)"


async def run(query, console, brain=None, memory=None):
    parts = query.strip().split()
    seconds = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10

    console.print(f"  [bold #f59e0b]⏱ Timer: {seconds}s[/bold #f59e0b]")

    for i in range(seconds, 0, -1):
        console.print(f"  [dim]{i}...[/dim]", end="\r")
        await asyncio.sleep(1)

    console.print(f"  [bold #10b981]⏱ Time's up! ({seconds}s)[/bold #10b981]\n")

    # Send notification if available
    import shutil
    if shutil.which("notify-send"):
        import subprocess
        subprocess.run(["notify-send", "Jarvis Timer", f"{seconds}s timer complete!"])

    return f"Timer: {seconds}s done"

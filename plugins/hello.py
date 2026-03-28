"""Example plugin — type 'hello' or 'hi' in Jarvis."""

COMMANDS = ["hello", "hi", "hey jarvis"]
DESCRIPTION = "Greet Jarvis"


async def run(query, console, brain=None, memory=None):
    console.print("  [bold #a78bfa]Hey! Jarvis here. What can I do for you?[/bold #a78bfa]\n")
    return "greeted"

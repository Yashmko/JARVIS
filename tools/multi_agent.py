from tools.shell_executor import ShellExecutor

class MultiAgent:
    def __init__(self, console):
        self.console = console
        self.shell = ShellExecutor(console)

    def _get_target(self):
        try:
            from tools.target_context import get_target
            t = get_target()
            if t:
                return t
        except:
            pass
        return "example.com"

    async def execute(self, query, target=None):
        if not target:
            target = self._get_target()

        task = query.lower()
        self.console.print("\n🤖 Multi-Agent Mode (real execution)\n")

        # API discovery
        if "api" in task:
            await self.shell.execute(f"subfinder -d {target} -silent > subs.txt")
            await self.shell.execute("grep -i api subs.txt | head -20")
            await self.shell.execute("httpx -l subs.txt -silent -path /api")
            return

        # Recon
        if "scan" in task or "recon" in task:
            await self.shell.execute(f"subfinder -d {target} -silent")
            await self.shell.execute(f"nmap -sV {target}")
            await self.shell.execute(f"nuclei -u https://{target}")
            return

        self.console.print("No deterministic chain matched.")

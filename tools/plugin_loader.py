"""
JARVIS v2 — tools/plugin_loader.py

Drop a .py file in plugins/ and Jarvis auto-loads it.

Plugin format:
  # plugins/my_plugin.py
  
  COMMANDS = ["mycommand", "mc"]  # triggers
  DESCRIPTION = "What my plugin does"
  
  async def run(query: str, console, brain=None, memory=None):
      console.print("Hello from my plugin!")
      return "done"
"""
import importlib.util
import logging
from pathlib import Path

log = logging.getLogger(__name__)

PLUGINS_DIR = Path("plugins")


class PluginManager:
    def __init__(self, console, brain=None, memory=None):
        self.console = console
        self.brain = brain
        self.memory = memory
        self.plugins: dict = {}
        self._load_all()

    def _load_all(self):
        """Load all .py files from plugins/"""
        if not PLUGINS_DIR.exists():
            PLUGINS_DIR.mkdir(exist_ok=True)
            return

        for f in sorted(PLUGINS_DIR.glob("*.py")):
            if f.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f.stem, f)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                commands = getattr(mod, "COMMANDS", [f.stem])
                desc = getattr(mod, "DESCRIPTION", f"Plugin: {f.stem}")
                run_fn = getattr(mod, "run", None)

                if run_fn:
                    for cmd in commands:
                        self.plugins[cmd.lower()] = {
                            "name": f.stem,
                            "description": desc,
                            "run": run_fn,
                            "file": str(f),
                        }
                    log.info(f"Plugin loaded: {f.stem} ({', '.join(commands)})")

            except Exception as e:
                log.warning(f"Plugin failed to load: {f.name}: {e}")

    def is_plugin_command(self, query: str) -> bool:
        """Check if query starts with any plugin command."""
        ql = query.lower().strip()
        first_word = ql.split()[0] if ql.split() else ""
        return first_word in self.plugins

    async def execute(self, query: str):
        """Run the matching plugin."""
        ql = query.lower().strip()
        first_word = ql.split()[0] if ql.split() else ""

        plugin = self.plugins.get(first_word)
        if not plugin:
            return None

        try:
            result = await plugin["run"](
                query, self.console,
                brain=self.brain, memory=self.memory
            )
            return result
        except Exception as e:
            self.console.print(f"  [red]Plugin error: {e}[/red]\n")
            return None

    def list_plugins(self) -> list:
        """Return list of loaded plugins."""
        seen = set()
        plugins = []
        for cmd, info in self.plugins.items():
            if info["name"] not in seen:
                seen.add(info["name"])
                plugins.append({
                    "name": info["name"],
                    "commands": [k for k, v in self.plugins.items() if v["name"] == info["name"]],
                    "description": info["description"],
                })
        return plugins

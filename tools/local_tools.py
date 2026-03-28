"""
JARVIS v2 — tools/local_tools.py
File operations, browser, editor, env management.
"""
import difflib
import os
import shutil
import subprocess
import time
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich.panel import Panel


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""


class LocalTools:
    def __init__(self, console: Console, base_dir: Optional[Path] = None):
        self.console = console
        self.base_dir = base_dir or Path.cwd()

    async def execute(self, query: str) -> ToolResult:
        q = query.strip()
        ql = q.lower()

        # ── FILE OPS ─────────────────────────────
        if ql.startswith("read "):
            return self.read_file(q[5:].strip())

        if ql.startswith("write "):
            parts = q[6:].strip().split(" ", 1)
            path = parts[0]
            content = parts[1].strip("\"'") if len(parts) > 1 else ""
            return self.write_file(path, content)

        if ql.startswith("append "):
            parts = q[7:].strip().split(" ", 1)
            path = parts[0]
            content = parts[1].strip("\"'") if len(parts) > 1 else ""
            return self.append_file(path, content)

        if ql.startswith(("delete ", "rm ")):
            path = q.split(" ", 1)[1].strip()
            return self.delete_file(path)

        if ql.startswith(("list files", "ls ", "list ")):
            path = q.split(" ", 1)[1].strip() if " " in q else "."
            path = path.replace("files", "").replace("in", "").strip() or "."
            return self.list_files(path)

        if ql.startswith("find "):
            return self.find_files(q[5:].strip())

        if ql.startswith(("rename ", "mv ")):
            parts = q.split(" ")[1:]
            if len(parts) >= 2:
                return self.rename_file(parts[0], parts[1])
            return ToolResult(False, error="Usage: rename old.txt new.txt")

        if ql.startswith(("copy ", "cp ")):
            parts = q.split(" ")[1:]
            if len(parts) >= 2:
                return self.copy_file(parts[0], parts[1])
            return ToolResult(False, error="Usage: copy src dst")

        if ql.startswith("mkdir "):
            return self.make_dir(q[6:].strip())

        if ql.startswith("tree"):
            path = q.split(" ", 1)[1].strip() if " " in q else "."
            return self.tree(path)

        if ql.startswith(("search ", "grep ")):
            return self.search_in_files(q.split(" ", 1)[1].strip())

        if ql.startswith("diff "):
            parts = q[5:].strip().split(" ", 1)
            if len(parts) == 2:
                return self.diff_files(parts[0], parts[1])
            return ToolResult(False, error="Usage: diff a.txt b.txt")

        if ql.startswith("zip "):
            parts = q[4:].strip().split(" ", 1)
            if len(parts) == 2:
                return self.zip_files(parts[0], parts[1])
            return ToolResult(False, error="Usage: zip source output.zip")

        if ql.startswith("unzip "):
            return self.unzip_file(q[6:].strip())

        # ── BROWSER ──────────────────────────────
        if ql.startswith(("browse ", "open http", "open www")):
            url = q.split(" ", 1)[1].strip()
            return self.browse(url)

        if "search" in ql and " on " in ql:
            return self.smart_search(q)

        if ql.startswith("search "):
            query_text = q[7:].strip().strip("\"'")
            return self.browse(f"https://duckduckgo.com/?q={quote_plus(query_text)}")

        # ── EDITOR ───────────────────────────────
        if ql.startswith("edit "):
            return self.open_in_editor(q[5:].strip())

        # ── ENV ──────────────────────────────────
        if ql in ("env list", "env"):
            return self.env_list()
        if ql.startswith("env get "):
            return self.env_get(q[8:].strip())
        if ql.startswith("env set "):
            parts = q[8:].strip().split(" ", 1)
            if len(parts) == 2:
                return self.env_set(parts[0], parts[1].strip("\"'"))
            return ToolResult(False, error="Usage: env set KEY value")

        if ql.startswith("which "):
            return self.which_binary(q[6:].strip())

        if ql in ("pip list", "pip freeze"):
            return self.pip_list()

        return ToolResult(False, error=f"Unknown local command: '{q}'")

    # ── FILE OPS ─────────────────────────────────
    def _resolve(self, path: str) -> Path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self.base_dir / p
        return p

    def read_file(self, path: str, max_chars: int = 8000) -> ToolResult:
        try:
            p = self._resolve(path)
            if not p.exists():
                return ToolResult(False, error=f"File not found: {path}")
            content = p.read_text(errors="replace")
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n[... truncated at {max_chars} chars]"

            ext = p.suffix.lstrip(".")
            lang_map = {"py": "python", "js": "javascript", "ts": "typescript",
                       "json": "json", "md": "markdown", "sh": "bash",
                       "yaml": "yaml", "yml": "yaml", "html": "html",
                       "css": "css", "rs": "rust", "go": "go", "toml": "toml"}
            lang = lang_map.get(ext, "text")
            self.console.print(Syntax(content, lang, theme="monokai",
                                     line_numbers=True, word_wrap=False))
            return ToolResult(True, output=content)
        except Exception as e:
            return ToolResult(False, error=str(e))

    def write_file(self, path: str, content: str) -> ToolResult:
        try:
            p = self._resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return ToolResult(True, output=f"Written: {path} ({p.stat().st_size} bytes)")
        except Exception as e:
            return ToolResult(False, error=str(e))

    def append_file(self, path: str, content: str) -> ToolResult:
        try:
            p = self._resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a") as f:
                f.write(content if content.endswith("\n") else content + "\n")
            return ToolResult(True, output=f"Appended to: {path}")
        except Exception as e:
            return ToolResult(False, error=str(e))

    def delete_file(self, path: str) -> ToolResult:
        p = self._resolve(path)
        if not p.exists():
            return ToolResult(False, error=f"Not found: {path}")
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return ToolResult(True, output=f"Deleted: {path}")

    def list_files(self, path: str = ".") -> ToolResult:
        try:
            p = self._resolve(path)
            if not p.exists():
                return ToolResult(False, error=f"Path not found: {path}")

            entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            t = Table(border_style="dim #374151", header_style="dim #4b5563",
                     show_lines=False, padding=(0, 2))
            t.add_column("Name", style="#5eead4")
            t.add_column("Type", style="dim", justify="center")
            t.add_column("Size", style="dim", justify="right")

            lines = []
            for entry in entries[:100]:
                stat = entry.stat()
                size = self._human_size(stat.st_size) if entry.is_file() else ""
                etype = "DIR" if entry.is_dir() else entry.suffix[1:].upper() or "FILE"
                t.add_row(entry.name, etype, size)
                lines.append(entry.name)

            self.console.print(t)
            return ToolResult(True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(False, error=str(e))

    def find_files(self, pattern: str) -> ToolResult:
        parts = pattern.split(" in ")
        glob_pat = parts[0].strip()
        search_dir = parts[1].strip() if len(parts) > 1 else "."
        try:
            base = self._resolve(search_dir)
            matches = list(base.rglob(glob_pat))
            if not matches:
                return ToolResult(True, output=f"No files matching '{glob_pat}'")
            lines = [str(m.relative_to(base) if base in m.parents or m.parent == base else m)
                    for m in sorted(matches)[:50]]
            output = "\n".join(lines)
            self.console.print(Text(output, style="#5eead4"))
            return ToolResult(True, output=output)
        except Exception as e:
            return ToolResult(False, error=str(e))

    def rename_file(self, src: str, dst: str) -> ToolResult:
        try:
            self._resolve(src).rename(self._resolve(dst))
            return ToolResult(True, output=f"Renamed: {src} → {dst}")
        except Exception as e:
            return ToolResult(False, error=str(e))

    def copy_file(self, src: str, dst: str) -> ToolResult:
        try:
            s = self._resolve(src)
            d = self._resolve(dst)
            if s.is_dir():
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
            return ToolResult(True, output=f"Copied: {src} → {dst}")
        except Exception as e:
            return ToolResult(False, error=str(e))

    def make_dir(self, path: str) -> ToolResult:
        try:
            self._resolve(path).mkdir(parents=True, exist_ok=True)
            return ToolResult(True, output=f"Created: {path}/")
        except Exception as e:
            return ToolResult(False, error=str(e))

    def tree(self, path: str = ".", max_depth: int = 3) -> ToolResult:
        p = self._resolve(path)
        lines = [str(p)]

        def _walk(dir_path, prefix, depth):
            if depth > max_depth:
                return
            try:
                items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return
            for i, item in enumerate(items[:40]):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{item.name}")
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    _walk(item, prefix + extension, depth + 1)

        _walk(p, "", 0)
        output = "\n".join(lines)
        self.console.print(Text(output, style="#5eead4"))
        return ToolResult(True, output=output)

    def search_in_files(self, query: str) -> ToolResult:
        import re
        m = re.match(r'"(.+?)"\s+in\s+(.+)', query)
        if not m:
            return ToolResult(False, error='Usage: search "pattern" in *.py')
        pattern = m.group(1)
        target = m.group(2).strip()
        base = self._resolve(".")
        results = []

        if "*" in target or "?" in target:
            files = list(base.rglob(target))
        else:
            p = self._resolve(target)
            files = list(p.rglob("*")) if p.is_dir() else [p]

        for f in files:
            if not f.is_file():
                continue
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if pattern.lower() in line.lower():
                        results.append(f"{f.relative_to(base)}:{i}: {line.strip()}")
            except Exception:
                pass

        if not results:
            return ToolResult(True, output=f"No matches for '{pattern}'")
        output = "\n".join(results[:100])
        self.console.print(Text(output, style="#9ca3af"))
        return ToolResult(True, output=output)

    def diff_files(self, a: str, b: str) -> ToolResult:
        try:
            fa = self._resolve(a).read_text(errors="replace").splitlines(keepends=True)
            fb = self._resolve(b).read_text(errors="replace").splitlines(keepends=True)
            diff = list(difflib.unified_diff(fa, fb, fromfile=a, tofile=b))
            if not diff:
                return ToolResult(True, output="Files are identical.")
            output = "".join(diff)
            self.console.print(Syntax(output, "diff", theme="monokai"))
            return ToolResult(True, output=output)
        except Exception as e:
            return ToolResult(False, error=str(e))

    def zip_files(self, source: str, output: str) -> ToolResult:
        try:
            src = self._resolve(source)
            out = self._resolve(output)
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                if src.is_dir():
                    for f in src.rglob("*"):
                        if f.is_file():
                            zf.write(f, f.relative_to(src.parent))
                else:
                    zf.write(src, src.name)
            return ToolResult(True, output=f"Created {output} ({self._human_size(out.stat().st_size)})")
        except Exception as e:
            return ToolResult(False, error=str(e))

    def unzip_file(self, path: str) -> ToolResult:
        try:
            p = self._resolve(path)
            out = p.parent / p.stem
            with zipfile.ZipFile(p) as zf:
                zf.extractall(out)
            return ToolResult(True, output=f"Extracted to {out}/")
        except Exception as e:
            return ToolResult(False, error=str(e))

    # ── BROWSER ──────────────────────────────────
    def browse(self, url: str) -> ToolResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            webbrowser.open(url)
            return ToolResult(True, output=f"Opened: {url}")
        except Exception as e:
            return ToolResult(False, error=str(e))

    def smart_search(self, query: str) -> ToolResult:
        import re
        m = re.search(r'search\s+"(.+?)"\s+on\s+(\w+)', query, re.IGNORECASE)
        if not m:
            terms = query.replace("search", "").strip().strip("\"'")
            return self.browse(f"https://duckduckgo.com/?q={quote_plus(terms)}")

        terms = m.group(1)
        platform = m.group(2).lower()
        url_map = {
            "google": f"https://google.com/search?q={quote_plus(terms)}",
            "github": f"https://github.com/search?q={quote_plus(terms)}",
            "youtube": f"https://youtube.com/results?search_query={quote_plus(terms)}",
            "pypi": f"https://pypi.org/search/?q={quote_plus(terms)}",
            "npm": f"https://www.npmjs.com/search?q={quote_plus(terms)}",
            "reddit": f"https://reddit.com/search/?q={quote_plus(terms)}",
            "stackoverflow": f"https://stackoverflow.com/search?q={quote_plus(terms)}",
        }
        url = url_map.get(platform, f"https://duckduckgo.com/?q={quote_plus(terms + ' ' + platform)}")
        return self.browse(url)

    # ── EDITOR ───────────────────────────────────
    def open_in_editor(self, spec: str) -> ToolResult:
        if " with " in spec.lower():
            parts = spec.split(" with ", 1)
            path = parts[0].strip()
            editor = parts[1].strip().lower()
        else:
            path = spec.strip()
            editor = None

        editors = {"code": "code", "vscode": "code", "vim": "vim",
                  "nvim": "nvim", "nano": "nano", "cursor": "cursor"}

        if editor and editor in editors:
            binary = editors[editor]
        else:
            env_editor = os.environ.get("EDITOR", "")
            candidates = [env_editor, "code", "cursor", "vim", "nano"]
            binary = next((c for c in candidates if c and shutil.which(c)), "")

        if not binary or not shutil.which(binary):
            return ToolResult(False, error="No editor found. Set $EDITOR.")

        p = self._resolve(path)
        try:
            subprocess.Popen([binary, str(p)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return ToolResult(True, output=f"Opened {path} in {binary}")
        except Exception as e:
            return ToolResult(False, error=str(e))

    # ── ENV ──────────────────────────────────────
    def env_list(self) -> ToolResult:
        safe = {k: v for k, v in os.environ.items()
               if not any(s in k.upper() for s in ("KEY", "SECRET", "TOKEN", "PASSWORD"))}
        lines = [f"{k}={v}" for k, v in sorted(safe.items())[:40]]
        output = "\n".join(lines)
        self.console.print(Text(output, style="dim #9ca3af"))
        return ToolResult(True, output=output)

    def env_get(self, key: str) -> ToolResult:
        val = os.environ.get(key.upper())
        if val is None:
            return ToolResult(False, error=f"Not set: {key}")
        if any(s in key.upper() for s in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
            masked = val[:4] + "****" if len(val) > 4 else "****"
            return ToolResult(True, output=f"{key}={masked}")
        return ToolResult(True, output=f"{key}={val}")

    def env_set(self, key: str, value: str) -> ToolResult:
        env_path = self.base_dir / ".env"
        lines = env_path.read_text().splitlines() if env_path.exists() else []
        key_upper = key.upper()
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key_upper}="):
                lines[i] = f"{key_upper}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key_upper}={value}")
        env_path.write_text("\n".join(lines) + "\n")
        os.environ[key_upper] = value
        return ToolResult(True, output=f"Set {key_upper}={value[:20]}{'...' if len(value)>20 else ''}")

    def which_binary(self, name: str) -> ToolResult:
        path = shutil.which(name)
        if path:
            return ToolResult(True, output=f"{name} → {path}")
        return ToolResult(False, error=f"'{name}' not found in PATH")

    def pip_list(self) -> ToolResult:
        r = subprocess.run(["pip", "list", "--format=columns"],
                         capture_output=True, text=True)
        self.console.print(Text(r.stdout[:3000], style="dim #9ca3af"))
        return ToolResult(True, output=r.stdout)

    @staticmethod
    def _human_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f}{unit}"
            n /= 1024
        return f"{n:.0f}TB"


LOCAL_PREFIXES = (
    "read ", "write ", "append ", "delete ", "rm ",
    "list files", "ls ", "list ", "find ", "rename ", "mv ",
    "copy ", "cp ", "mkdir ", "tree", "search ", "grep ",
    "diff ", "zip ", "unzip ", "browse ", "open http", "open www",
    "edit ", "env ", "which ", "pip list", "pip freeze",
)


def is_local_command(query: str) -> bool:
    ql = query.lower().strip()
    return any(ql.startswith(p) for p in LOCAL_PREFIXES)

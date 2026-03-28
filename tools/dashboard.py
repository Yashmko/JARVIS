"""
JARVIS v2 — tools/dashboard.py

Rich visual dashboard. Command: stats or dashboard
Shows: tasks, providers, skills, RAM, routes, daily summary.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.align import Align


class Dashboard:
    def __init__(self, console: Console, memory, settings):
        self.console = console
        self.memory = memory
        self.settings = settings

    def render(self):
        stats = self.memory.get_stats()
        self.console.print()

        # ── HEADER ────────────────────────────────
        self.console.print(Align.center(
            Text("  JARVIS v2 — Dashboard  ", style="bold #f8fafc on #6d28d9")
        ))
        self.console.print()

        # ── SUMMARY CARDS ─────────────────────────
        panels = []

        # Tasks
        panels.append(Panel(
            Text(f"{stats['total']}", style="bold #5eead4", justify="center") +
            Text(f"\ntasks ({stats['profile']})", style="dim", justify="center"),
            border_style="dim #374151", padding=(0, 2), width=18
        ))

        # Total all
        panels.append(Panel(
            Text(f"{stats['total_all']}", style="bold white", justify="center") +
            Text("\ntotal all profiles", style="dim", justify="center"),
            border_style="dim #374151", padding=(0, 2), width=18
        ))

        # Tokens
        panels.append(Panel(
            Text(f"{stats['total_tokens']:,}", style="bold #a78bfa", justify="center") +
            Text("\ntokens used", style="dim", justify="center"),
            border_style="dim #374151", padding=(0, 2), width=18
        ))

        # RAM
        ram = stats['ram_mb']
        ram_color = "#10b981" if ram < 200 else "#f59e0b" if ram < 400 else "#ef4444"
        panels.append(Panel(
            Text(f"{ram}MB", style=f"bold {ram_color}", justify="center") +
            Text("\nRAM usage", style="dim", justify="center"),
            border_style="dim #374151", padding=(0, 2), width=18
        ))

        # DB Size
        panels.append(Panel(
            Text(f"{stats['db_size_mb']}MB", style="bold white", justify="center") +
            Text("\ndatabase", style="dim", justify="center"),
            border_style="dim #374151", padding=(0, 2), width=18
        ))

        self.console.print(Columns(panels, equal=False, padding=0))
        self.console.print()

        # ── PROVIDER USAGE ────────────────────────
        if stats['providers']:
            pt = Table(title="[bold #a78bfa]Provider Usage[/bold #a78bfa]",
                      border_style="dim #374151", header_style="dim #4b5563",
                      padding=(0, 1))
            pt.add_column("Provider", style="cyan", no_wrap=True)
            pt.add_column("Tokens", justify="right")
            pt.add_column("% of total", justify="right")
            pt.add_column("Bar", min_width=20)

            total_tok = stats['total_tokens'] or 1
            max_tok = max(stats['providers'].values()) if stats['providers'] else 1

            for prov, toks in sorted(stats['providers'].items(), key=lambda x: -x[1]):
                pct = f"{toks/total_tok*100:.1f}%"
                bar_len = int(toks / max_tok * 20)
                bar = "[#5eead4]" + "█" * bar_len + "[/#5eead4]" + "[dim]" + "░" * (20 - bar_len) + "[/dim]"
                pt.add_row(prov, f"{toks:,}", pct, bar)

            self.console.print(pt)
            self.console.print()

        # ── TOP SKILLS ────────────────────────────
        top = stats.get("top_skills", [])
        if top:
            st = Table(title="[bold #a78bfa]Top Skills[/bold #a78bfa]",
                      border_style="dim #374151", header_style="dim #4b5563",
                      padding=(0, 1))
            st.add_column("Skill", style="cyan", no_wrap=True, max_width=35)
            st.add_column("Uses", justify="right")
            st.add_column("Success", justify="right")
            st.add_column("Bar", min_width=15)

            max_uses = top[0][1] if top else 1
            for skill, uses, success in top[:12]:
                if not skill:
                    continue
                pct = f"{success/uses*100:.0f}%" if uses else "—"
                bar_len = int(uses / max_uses * 15)
                sty = "#10b981" if (uses and success/uses > 0.8) else "#f59e0b"
                bar = f"[{sty}]" + "█" * bar_len + f"[/{sty}]" + "[dim]" + "░" * (15 - bar_len) + "[/dim]"
                st.add_row(skill, str(uses), pct, bar)

            self.console.print(st)
            self.console.print()

        # ── ROUTING QUALITY ───────────────────────
        router_log = self.settings.SKILL_INDEX_PATH.parent / "router.log"
        if router_log.exists():
            scores = []
            try:
                for line in router_log.read_text().splitlines()[-200:]:
                    entry = json.loads(line)
                    scores.append(entry.get("score", 0))
            except Exception:
                pass

            if scores:
                avg = sum(scores) / len(scores)
                high = sum(1 for s in scores if s >= 0.7)
                high_pct = high / len(scores) * 100

                quality_color = "#10b981" if high_pct >= 80 else "#f59e0b" if high_pct >= 60 else "#ef4444"
                quality_msg = "Excellent" if high_pct >= 80 else "Good" if high_pct >= 60 else "Needs tuning"

                rp = Panel(
                    f"[bold]Routing Quality:[/bold] [{quality_color}]{quality_msg}[/{quality_color}]\n"
                    f"Total routes: {len(scores)}\n"
                    f"Avg confidence: {avg:.0%}\n"
                    f"High confidence (≥70%): {high_pct:.0f}%\n"
                    f"\n[dim]Run 'improve routing' to auto-fix low routes[/dim]",
                    title="[bold #a78bfa]Routing[/bold #a78bfa]",
                    border_style="dim #374151", padding=(0, 2)
                )
                self.console.print(rp)
                self.console.print()

        # ── DAILY SUMMARY ─────────────────────────
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        today_count = self.memory._conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE ts LIKE ? AND role='user'",
            (f"{today}%",)
        ).fetchone()[0]

        yesterday_count = self.memory._conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE ts LIKE ? AND role='user'",
            (f"{yesterday}%",)
        ).fetchone()[0]

        trend = "↑" if today_count > yesterday_count else "↓" if today_count < yesterday_count else "→"
        trend_color = "#10b981" if today_count >= yesterday_count else "#ef4444"

        self.console.print(
            f"  [dim]Today:[/dim] [bold]{today_count}[/bold] tasks  "
            f"[{trend_color}]{trend}[/{trend_color}]  "
            f"[dim]Yesterday:[/dim] {yesterday_count}"
        )

        # ── PROFILES ──────────────────────────────
        profiles = stats.get("profiles", [])
        if profiles:
            self.console.print(f"  [dim]Profiles:[/dim] {', '.join(profiles)}")

        self.console.print()


def is_multi_command(q: str) -> bool:
    return q.strip().lower().startswith("multi:")

"""
JARVIS v2 — main.py (FINAL)
All 30 features. Complete autonomous AI agent OS.
"""
import asyncio,sys,time,argparse
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.align import Align
from rich.rule import Rule

sys.path.insert(0, ".")
from brain import BrainClient
from router import Router
from executor import ExecutionEngine
from memory.memory import Memory
from context_injector import build_messages, MODE_PROMPTS
from config.settings import Settings
from config.profiles import get_profile, list_profiles, PROFILES
from tools.system_control import SystemController, is_sys_command
from tools.local_tools import LocalTools, is_local_command
from tools.skill_creator import SkillCreator, is_skill_create
from tools.bounty import BountyToolkit, is_bounty_command
from tools.report_gen import ReportGenerator, is_export_command
from tools.automation import AutomationTools, is_automation_command
from tools.plugin_loader import PluginManager
from tools.maintenance import MaintenanceTools, is_maintenance_command
from tools.dashboard import Dashboard
from tools.multi_agent import MultiAgent
from tools.browser_auto import BrowserAutomation, is_browser_command
from tools.autonomous import AutonomousAgent, is_auto_command
from tools.shell_executor import ShellExecutor, is_raw_shell_command
from tools.bounty_runner import BountyRunner
from tools.target_context import get_target_context
from tools.output_validator import safe_llm_response, is_hallucinated
from tools.safe_json import safe_parse_json



console = Console()
settings = Settings()

BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"""

GRADIENT = ["#4c1d95","#5b21b6","#6d28d9","#7c3aed","#8b5cf6","#a855f7","#c026d3"]
CAT_COLORS = {"security":"#ef4444","architecture":"#8b5cf6","data-ai":"#3b82f6",
    "development":"#10b981","infrastructure":"#f59e0b","testing":"#14b8a6",
    "workflow":"#f97316","business":"#ec4899","general":"#94a3b8"}

last_output = ""
last_skill = None

def print_banner(pname="default"):
    console.clear()
    art = Text()
    for i, line in enumerate(BANNER.strip("\n").splitlines()):
        art.append(line+"\n", style=f"bold {GRADIENT[min(i,len(GRADIENT)-1)]}")
    console.print(Align.center(art))
    b = Text()
    b.append("  v2.0 FINAL ", style="bold #f8fafc on #6d28d9")
    if pname != "default": b.append(f"  {pname.upper()} ", style="bold #f8fafc on #ef4444")
    b.append("  7 LLMs · 1,323 SKILLS · AUTONOMOUS · BOUNTY · PLUGINS", style="dim #a78bfa")
    console.print(Align.center(b))
    console.print()
    prov = Text()
    for n,k in [("groq",settings.GROQ_API_KEY),("cerebras",settings.CEREBRAS_API_KEY),
                ("gemini",settings.GEMINI_API_KEY),("together",settings.TOGETHER_API_KEY),
                ("mistral",settings.MISTRAL_API_KEY),("openrouter",settings.OPENROUTER_API_KEY),
                ("hf",settings.HF_API_KEY)]:
        prov.append(f"  {'●' if k else '○'} {n}", style="#10b981" if k else "#374151")
    console.print(Align.center(prov))
    console.print()
    bar = Text()
    for c in ["help","auto: <task>","bounty recon <d>","multi: <task>","dashboard","exit"]:
        bar.append(f"  {c}  ", style="#5eead4"); bar.append("│", style="dim #374151")
    console.print(Align.center(bar))
    console.print(Rule(style="dim #1f2937"))
    console.print()

async def boot_systems(router, memory, pcfg, plugins):
    mods = [
        ("brain.py",       "7 providers · fallback · streaming"),
        ("router.py",      f"fuzzy · {len(router.skills)} skills"),
        ("memory.py",      f"WAL SQLite · profile: {memory.get_profile()}"),
        ("executor.py",    "action mode · clean stream"),
        ("bounty.py",      "recon · headers · nuclei · report"),
        ("autonomous.py",  "self-executing agent loop"),
        ("multi_agent.py", "split tasks into sub-agents"),
        ("browser_auto.py","scrape · monitor · download"),
        ("automation.py",  "queue · cron · git · clipboard"),
        ("plugins/",       f"{len(plugins.plugins)} plugin commands"),
        ("telegram_bot.py","remote control (separate process)"),
        ("mcp.py",         "Claude/Cursor/VSCode integration"),
    ]
    for n,d in mods:
        t = Text(); t.append("  ▸ ", style="bold #f59e0b")
        t.append(f"{n:<20}", style="#8b5cf6"); t.append(d, style="dim #4b5563")
        console.print(t); await asyncio.sleep(0.02)
    console.print()
    mode = memory.kv_get("mode",pcfg.get("mode","act"))
    console.print(Text(f"  ✓ ALL SYSTEMS ONLINE  — {len(router.skills)} skills · mode: {mode}",
                       style="bold #10b981"))
    console.print()

def show_skill_match(m):
    c = CAT_COLORS.get(m.get("category","general"),"#94a3b8")
    console.print(Text(f"\n  ⚡ {m['name']}  [{m.get('category','')}]  {m.get('score',0):.0%}",style=f"bold {c}"))
    console.print()

def show_wf_start(wf):
    console.print()
    console.print(Text(f"  🔗 WORKFLOW  {wf['name']}  ·  {len(wf['steps'])} steps", style="bold #a78bfa"))
    for i,s in enumerate(wf["steps"],1): console.print(f"  [dim]  {i}. {s.get('label',s['skill'])}[/dim]")
    console.print()

def show_step(i,total,label,skill):
    bar = "█"*i+"░"*(total-i)
    console.print(f"\n  [bold #f59e0b]┌── Step {i}/{total}[/bold #f59e0b]  [bold]{label}[/bold]")
    console.print(f"  [#5eead4]│ [{bar}][/#5eead4]\n")

def show_step_done(ok,label,ms):
    icon = "[bold #10b981]✓[/bold #10b981]" if ok else "[bold #ef4444]✗[/bold #ef4444]"
    timing = f"{ms}ms" if ms<1000 else f"{ms/1000:.1f}s"
    console.print(f"  └── {icon} {label}  [dim]{timing}[/dim]")

async def stream_to_terminal(messages, brain):
    output = ""; current_line = ""
    async for chunk in brain.stream(messages):
        output += chunk; current_line += chunk
        while "\n" in current_line:
            line, current_line = current_line.split("\n",1)
            console.print(f"  {line}")
    if current_line.strip(): console.print(f"  {current_line}")
    console.print(); return output

def show_help(memory, plugins):
    mode = memory.kv_get("mode","act"); profile = memory.get_profile()
    t = Table(title=f"[bold #a78bfa]JARVIS v2 FINAL[/bold #a78bfa]  mode:{mode}  profile:{profile}",
              border_style="dim #1f2937",header_style="dim #4b5563",show_lines=False,padding=(0,2))
    t.add_column("Command", style="#5eead4", no_wrap=True)
    t.add_column("What it does", style="dim #9ca3af")
    for cmd,desc in [
        ("── Autonomous ──",""),
        ("auto: <task>","Agent runs commands autonomously"),
        ("agent: <task>","Same as auto:"),
        ("── Multi-Agent ──",""),
        ("multi: <complex task>","Split into sub-agents"),
        ("── Bounty ──",""),
        ("bounty recon/headers/tech/ports/nuclei <d>","Recon tools"),
        ("bounty workflow <d> / report / programs","Full pipeline"),
        ("── Browser ──",""),
        ("scrape <url> / scrape links/emails <url>","Web scraping"),
        ("monitor <url> / download <url> <file>","Monitor & download"),
        ("── Queue & Cron ──",""),
        ("queue: <task> / run queue","Task queue"),
        ("every <N> <unit> run: <cmd>","Recurring tasks"),
        ("── Git ──",""),
        ("git status/diff/log/commit/push/branch","Git operations"),
        ("── Automation ──",""),
        ("clipboard copy/paste / chain: a > b > c","Clipboard & chains"),
        ("── Telegram ──",""),
        ("(run separately) python tools/telegram_bot.py","Phone control"),
        ("── Dashboard ──",""),
        ("dashboard / stats","Visual stats"),
        ("── Maintenance ──",""),
        ("backup memory / vacuum db / maintenance","DB maintenance"),
        ("── Skills ──",""),
        ("skills list/search/info · create a skill for X","Management"),
        ("mode act/concise/detailed/creative/minimal","Response mode"),
        ("profile bugbounty/coding/personal/automation","Switch profile"),
        ("pin/pins/unpin · export last/memory · plugins","Context & export"),
        ("open/run:/sysinfo/read/write/find/edit/tree","System & files"),
        ("history/workflows/improve routing/help/exit",""),
    ]: t.add_row(cmd,desc)
    console.print(); console.print(Align.center(t))
    plist = plugins.list_plugins()
    if plist:
        console.print()
        for p in plist: console.print(f"  [#5eead4]{', '.join(p['commands']):<20}[/#5eead4] [dim]{p['description']}[/dim]")
    console.print()

def handle_skills(query,router):
    import json; parts = query.strip().split(); sub = parts[1] if len(parts)>1 else "list"
    if sub == "list":
        cat = parts[2] if len(parts)>2 else None; skills = router.list_skills(category=cat)
        t = Table(title=f"Skills ({len(skills)})",border_style="dim #1f2937",padding=(0,1))
        t.add_column("Name",style="cyan",no_wrap=True); t.add_column("Cat",style="magenta"); t.add_column("Desc")
        for s in skills[:60]: t.add_row(s.get("name",""),s.get("category",""),s.get("description","")[:70])
        if len(skills)>60: t.add_row(f"...{len(skills)-60} more","","")
        console.print(); console.print(t); console.print()
    elif sub=="search" and len(parts)>2:
        q=" ".join(parts[2:]); results=router.search_skills(q,k=8)
        t = Table(title=f'Search: "{q}"',border_style="dim #1f2937",padding=(0,1))
        t.add_column("Score",justify="right",style="yellow"); t.add_column("Name",style="cyan"); t.add_column("Cat")
        for r in results: t.add_row(f"{r['score']:.0%}",r.get("name",""),r.get("category",""))
        console.print(); console.print(t); console.print()
    elif sub=="info" and len(parts)>2:
        s=router.skill_info(parts[2])
        if s: console.print_json(json.dumps(s,indent=2))
        else: console.print("[yellow]Not found[/yellow]")
        console.print()
    else: console.print("  [dim]skills list/search/info[/dim]\n")

def handle_history(memory,n=20):
    rows=memory.get_history(n)
    if not rows: console.print("  [dim]No history.[/dim]\n"); return
    t=Table(title=f"Last {len(rows)}",border_style="dim #1f2937",padding=(0,1))
    t.add_column("Date",style="dim"); t.add_column("Task"); t.add_column("Skill",style="cyan"); t.add_column("Out",style="green")
    for ts,task,skill,out in reversed(rows): t.add_row(ts[:10],task[:50],skill or "—",out or "—")
    console.print(); console.print(t); console.print()

def load_workflows():
    import json; from pathlib import Path; wfs={}
    for f in Path("workflows").glob("*.json"):
        try:
            wf=json.loads(f.read_text())
            if "name" in wf and "triggers" in wf and "steps" in wf: wfs[f.stem]=wf
        except: pass
    return wfs

def detect_workflow(q,wfs):
    ql=q.lower()
    for wf in wfs.values():
        for trigger in wf.get("triggers",[]):
            if trigger.lower() in ql: return wf
    return None

async def main_loop():
    global last_output,last_skill
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile","-p",default="default")
    for p in ["lite","full","safe","bugbounty","coding","personal","automation"]:
        parser.add_argument(f"--{p}",action="store_const",const=p,dest="profile")
    args,_=parser.parse_known_args()
    pcfg=get_profile(args.profile)
    print_banner(args.profile)

    memory=Memory(window=settings.MEMORY_WINDOW,db_path=settings.MEMORY_DB,
                  profile=pcfg.get("memory_profile","default"))
    memory.kv_set("mode",pcfg.get("mode","act"))
    persona=settings.PERSONA+pcfg.get("extra_persona","")

    brain=BrainClient(settings); router=Router(settings); executor=ExecutionEngine(settings)
    workflows=load_workflows()
    sys_ctrl=SystemController(console); local_tools=LocalTools(console,base_dir=settings.SKILLS_DIR.parent)
    skill_creator=SkillCreator(brain,settings.SKILLS_DIR,console,settings)
    bounty=BountyToolkit(console,brain=brain); report_gen=ReportGenerator(console,memory)
    automation=AutomationTools(console); plugins=PluginManager(console,brain=brain,memory=memory)
    maint=MaintenanceTools(console,memory=memory); dash=Dashboard(console,memory,settings)
    multi=MultiAgent(console,brain,router,memory,settings,persona,stream_to_terminal,build_messages)
    browser=BrowserAutomation(console)
    autonomous=AutonomousAgent(console,brain,sys_ctrl,memory,settings,persona)

    await boot_systems(router,memory,pcfg,plugins)

    async def run_query(q):
        global last_output,last_skill
        if is_sys_command(q): await sys_ctrl.execute(q)
        elif is_bounty_command(q): await bounty.execute(q)
        elif is_local_command(q): await local_tools.execute(q)
        else:
            match=router.route(q); msgs=build_messages(q,memory,persona,skill=match,settings=settings)
            await stream_to_terminal(msgs,brain)
            memory.add("user",q,skill=match["name"] if match else None,outcome="success")

    while True:
        try: console.print(Text("  ▶ ",style="bold #8b5cf6"),end=""); query=input()
        except (KeyboardInterrupt,EOFError): console.print("\n  [dim]bye.[/dim]\n"); break
        query=query.strip(); q_low=query.lower()
        if not query: continue
        # ── Kimi K2.5 direct modes (must be before router) ──────────
        if q_low.startswith("kimi think:"):
            prompt = query[11:].strip()
            try:
                from tools.kimi_swarm import get_kimi
                kimi = get_kimi(settings)
                console.print("  [bold cyan]🧠 Kimi K2.5 — Thinking Mode[/bold cyan]\n")
                answer, reasoning = kimi.think(prompt)
                if reasoning:
                    console.print(f"  [dim]Reasoning trace: {reasoning[:300]}...[/dim]\n")
                console.print(f"  {answer}\n")
            except Exception as e:
                console.print(f"  [red]Kimi error: {e}[/red]\n")
            continue

        if q_low.startswith("kimi agent:"):
            prompt = query[11:].strip()
            try:
                from tools.kimi_swarm import get_kimi
                kimi = get_kimi(settings)
                console.print("  [bold yellow]🤖 Kimi K2.5 — Agent Mode (real shell)[/bold yellow]\n")
                result = kimi.agent(prompt)
                console.print(f"  {result}\n")
            except Exception as e:
                console.print(f"  [red]Kimi error: {e}[/red]\n")
            continue

        if q_low.startswith("kimi swarm:"):
            prompt = query[11:].strip()
            try:
                from tools.kimi_swarm import get_kimi
                kimi = get_kimi(settings)
                console.print("  [bold magenta]🐝 Kimi K2.5 — SWARM Mode (100 parallel agents)[/bold magenta]\n")
                result = kimi.swarm(prompt)
                console.print(f"  {result}\n")
            except Exception as e:
                console.print(f"  [red]Kimi error: {e}[/red]\n")
            continue

        if q_low.startswith("kimi:"):
            prompt = query[5:].strip()
            try:
                from tools.kimi_swarm import get_kimi
                kimi = get_kimi(settings)
                result = kimi.instant(prompt)
                console.print(f"  {result}\n")
            except Exception as e:
                console.print(f"  [red]Kimi error: {e}[/red]\n")
            continue


        if q_low in ("exit","quit","q"):
            console.print(Align.center(Text("\n  goodbye  \n",style="bold #f8fafc on #6d28d9"))); break
        if q_low=="clear": print_banner(args.profile); continue
        if q_low=="help": show_help(memory,plugins); continue

        # Mode
        if q_low.startswith("mode "):
            m=q_low.split(" ",1)[1].strip()
            if m in MODE_PROMPTS: memory.kv_set("mode",m); console.print(f"  [bold #10b981]✓ Mode: {m}[/bold #10b981]\n")
            else: console.print(f"  [dim]Modes: {', '.join(MODE_PROMPTS.keys())}[/dim]\n")
            continue
        if q_low.startswith("jarvis be "):
            m=q_low.replace("jarvis be ","").strip()
            if m in MODE_PROMPTS: memory.kv_set("mode",m); console.print(f"  [bold #10b981]✓ Mode: {m}[/bold #10b981]\n")
            continue

        # Profile
        if q_low.startswith("profile "):
            p=q_low.split(" ",1)[1].strip()
            if p in PROFILES:
                pc=get_profile(p); memory.set_profile(pc.get("memory_profile","default"))
                memory.kv_set("mode",pc.get("mode","act")); persona=settings.PERSONA+pc.get("extra_persona","")
                console.print(f"  [bold #10b981]✓ Profile: {p}[/bold #10b981] [dim]{pc.get('description','')}[/dim]\n")
            else: console.print(f"  [dim]Profiles: {', '.join(PROFILES.keys())}[/dim]\n")
            continue
        if q_low=="profiles":
            for n,d in list_profiles().items(): console.print(f"  [#5eead4]{n:<15}[/#5eead4] [dim]{d}[/dim]")
            console.print(); continue

        # Pins
        if q_low.startswith("pin "): memory.pin(query[4:].strip()); console.print("  [bold #10b981]✓ Pinned[/bold #10b981]\n"); continue
        if q_low=="pins":
            pins=memory.get_pins()
            if not pins: console.print("  [dim]No pins.[/dim]\n")
            else:
                for pid,c in pins: console.print(f"  [#5eead4]#{pid}[/#5eead4] {c}")
                console.print()
            continue
        if q_low.startswith("unpin"):
            parts=q_low.split()
            if len(parts)>1 and parts[1].isdigit(): memory.unpin(int(parts[1]))
            else: memory.unpin()
            console.print("  [dim]✓ Unpinned[/dim]\n"); continue

        # Dashboard
        if q_low in ("dashboard","stats","dash"): dash.render(); continue

        # Plugins
        if q_low=="plugins":
            plist=plugins.list_plugins()
            if not plist: console.print("  [dim]No plugins. Drop .py in plugins/[/dim]\n")
            else:
                for p in plist: console.print(f"  [#5eead4]{', '.join(p['commands']):<20}[/#5eead4] [dim]{p['description']}[/dim]")
                console.print()
            continue
        if plugins.is_plugin_command(query):
            await plugins.execute(query); memory.add("user",query,skill="plugin",outcome="success"); continue

        # Autonomous
        if is_auto_command(query):
            console.print(); result=await autonomous.execute(query)
            last_output=result; last_skill="autonomous-agent"; continue

        # Multi-agent
        if is_multi_command(query):
            console.print(); result=await multi.execute(query)
            last_output=result; last_skill="multi-agent"
            memory.add("user",query,skill="multi-agent",outcome="success"); continue

        # Browser automation
        if is_browser_command(query):
            console.print(); result=await browser.execute(query)
            if result.error: console.print(Text(f"  ✗ {result.error}\n",style="bold #ef4444"))
            memory.add("user",query,skill="browser-auto",outcome="success" if result.success else "error"); continue

        # Automation
        if is_automation_command(query):
            console.print(); result=await automation.execute(query,run_fn=run_query)
            if result.error: console.print(Text(f"  ✗ {result.error}\n",style="bold #ef4444"))
            memory.add("user",query,skill="automation",outcome="success" if result.success else "error")
            if q_low.startswith("chain"): workflows=load_workflows()
            continue

        # Bounty
        if is_bounty_command(query):
            console.print(); result=await bounty.execute(query)
            if result.error: console.print(Text(f"\n  {result.error}\n",style="#ef4444"))
            memory.add("user",query,skill="bounty-toolkit",outcome="success" if result.success else "error"); continue

        # Export
        if is_export_command(query):
            sub=q_low.replace("export ","").strip()
            if sub=="last": report_gen.export_last(last_output,last_skill)
            elif sub=="memory": report_gen.export_memory()
            elif sub=="report": await bounty.generate_report()
            else: console.print("  [dim]export last | memory | report[/dim]\n")
            continue

        # Maintenance
        if is_maintenance_command(query): console.print(); await maint.execute(query); continue

        # Improve
        if q_low in ("improve routing","improve","auto improve"):
            console.print(); import subprocess; subprocess.run([sys.executable,"tools/auto_improve.py"]); console.print(); continue

        # Standard
        if q_low.startswith("history"):
            parts=q_low.split(); n=int(parts[1]) if len(parts)>1 and parts[1].isdigit() else 20
            handle_history(memory,n); continue
        if q_low.startswith("skills"): handle_skills(query,router); continue
        if q_low=="workflows":
            wfs=load_workflows()
            if not wfs: console.print("  [dim]No workflows.[/dim]\n")
            else:
                for wf in wfs.values():
                    console.print(f"\n  [bold #a78bfa]{wf['name']}[/bold #a78bfa]  ·  {len(wf['steps'])} steps")
                    console.print(f"  [dim]Triggers: {', '.join(wf['triggers'][:3])}[/dim]")
                console.print()
            continue
        if q_low.startswith("forget"):
            target=q_low.split(" ",1)[1] if " " in q_low else "last"
            memory.forget(target); console.print(f"  [dim]✓ Forgot: {target}[/dim]\n"); continue

        # Self-learning
        if is_skill_create(query):
            console.print(); result=await skill_creator.handle(query,conversation_history=memory.short_term())
            console.print(Text(f"\n  {result}\n",style="dim #6b7280"))
            memory.add("user",query,skill="skill-creator",outcome="success"); continue

        # System control
        if is_sys_command(query):
            console.print(); result=await sys_ctrl.execute(query)
            if result.output: console.print(Text(f"\n  {result.output}\n",style="#e2e8f0"))
            elif result.error: console.print(Text(f"\n  ✗ {result.error}\n",style="bold #ef4444"))
            memory.add("user",query,skill="system-control",outcome="success" if result.success else "error"); continue

        # Local tools
        if is_raw_shell_command(query):
            _shell = ShellExecutor(console)
            _sr = await _shell.execute(query)
            if _sr.output and _sr.output != "(no output)":
                memory.add("user", query, skill="shell", outcome="success")
            continue
        if is_local_command(query):
            console.print(); result=await local_tools.execute(query)
            if result.error: console.print(Text(f"\n  ✗ {result.error}\n",style="bold #ef4444"))
            memory.add("user",query,skill="local-tools",outcome="success" if result.success else "error"); continue

        # Classify + route
        console.print()
        # ── BOUNTY RECON (real tools, no LLM) ──────────────────
        _ql = query.lower().strip()
        _bounty_triggers = (
            "bounty recon", "bug bounty", "real recon",
            "full recon", "start recon",
        )
        _bounty_exact = (
            "security audit", "pentest", "do a security audit",
            "do security audit", "do a security audit on the target",
        )
        if (any(_ql.startswith(t) for t in _bounty_triggers) or
                any(_ql == t or _ql.startswith(t + " ") for t in _bounty_exact)):
            _tctx2 = get_target_context()
            _bt = _tctx2.get_target()
            import re as _re2
            _dm2 = _re2.search(
                r"[\w\-]+\.(?:com|org|net|io|co|app|dev|gov|edu|uk)",
                query
            )
            if _dm2:
                _bt = _dm2.group(0)
                _tctx2.set_target(_bt)
            if not _bt:
                console.print("  [bold #f59e0b]Set a target first: target example.com[/bold #f59e0b]\n")
            else:
                _runner = BountyRunner(console)
                await _runner.run_full_recon(_bt)
                memory.add("user", query, skill="bounty-runner", outcome="success")
            continue

        # ── URL FETCH + AUTO EXECUTE ─────────────────────────────
        import re as _urlre
        _url_match = _urlre.search(r'https?://[^\s]+', query)
        if _url_match and not is_raw_shell_command(query):
            _url = _url_match.group(0).rstrip('.,)')
            console.print(f"  [dim]Fetching: {_url}[/dim]\n")
            try:
                import asyncio as _asyncio2
                _proc = await _asyncio2.create_subprocess_shell(
                    f"curl -s -L --max-time 20 "
                    f"-H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36' "
                    f"-H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' "
                    f"'{_url}'",
                    stdout=_asyncio2.subprocess.PIPE,
                    stderr=_asyncio2.subprocess.PIPE,
                )
                _stdout, _ = await _asyncio2.wait_for(_proc.communicate(), timeout=25)
                _raw = _stdout.decode(errors="replace")
                import re as _re3
                _text = _re3.sub(r"<script[^>]*>.*?</script>", " ", _raw, flags=_re3.DOTALL)
                _text = _re3.sub(r"<style[^>]*>.*?</style>", " ", _text, flags=_re3.DOTALL)
                _code_blocks = _re3.findall(r"<code[^>]*>(.*?)</code>", _text, flags=_re3.DOTALL)
                _pre_blocks = _re3.findall(r"<pre[^>]*>(.*?)</pre>", _text, flags=_re3.DOTALL)
                _text = _re3.sub(r"<[^>]+>", " ", _text)
                _text = _re3.sub(r"\s+", " ", _text).strip()
                _code_text = ""
                for _cb in _code_blocks[:10]:
                    _clean_cb = _re3.sub(r"<[^>]+>", "", _cb).strip()
                    if _clean_cb:
                        _code_text += f"\nCODE: {_clean_cb}\n"
                for _pb in _pre_blocks[:5]:
                    _clean_pb = _re3.sub(r"<[^>]+>", "", _pb).strip()
                    if _clean_pb:
                        _code_text += f"\nCOMMAND: {_clean_pb}\n"
                _full_content = _text[:2000] + _code_text[:2000]
                if len(_full_content.strip()) < 100:
                    _full_content = _raw[:3000]

                # Step 1: Get commands from LLM
                _fetch_msgs = [
                    {"role": "system", "content": (
                        "You extract shell commands from page content and output ONLY a numbered list of commands. "
                        "You are on Arch Linux — convert apt/apt-get to pacman, pip to pip --break-system-packages or venv. "
                        "Output ONLY the commands, one per line, no explanation, no markdown, no backticks. "
                        "Format: just the raw command on each line."
                    )},
                    {"role": "user", "content": (
                        f"Extract and convert to Arch Linux all install/setup commands from this page:\n{_full_content}"
                    )}
                ]
                _cmd_response = ""
                async for _chunk in brain.stream(_fetch_msgs):
                    _cmd_response += _chunk

                # Step 2: Parse commands
                _dangerous = ["rm -rf /", "mkfs", "dd if=/dev/zero", "shutdown", ":(){"]
                _skip = ["#", "//", "http", "expected", "output", "result", "note:", "---"]
                _commands = []
                for _line in _cmd_response.splitlines():
                    _l = _line.strip()
                    # Remove numbering like "1." "2." etc
                    _l = _re3.sub(r"^\d+\.\s*", "", _l).strip()
                    # Remove backticks
                    _l = _l.strip("`")
                    if not _l:
                        continue
                    if any(_l.lower().startswith(s) for s in _skip):
                        continue
                    if any(d in _l for d in _dangerous):
                        continue
                    if len(_l) > 5:
                        _commands.append(_l)

                if not _commands:
                    console.print("  [yellow]No executable commands found on page.[/yellow]\n")
                    memory.add("user", query, skill="url-fetch", outcome="no-commands")
                    continue

                # Step 3: Show plan and confirm
                console.print(f"  [bold #a78bfa]Found {len(_commands)} commands to run:[/bold #a78bfa]\n")
                for _ci, _cmd in enumerate(_commands, 1):
                    console.print(f"  [dim]{_ci}.[/dim] [#5eead4]{_cmd}[/#5eead4]")
                console.print()
                console.print("  [bold #f59e0b]Execute all? (yes/no/select):[/bold #f59e0b] ", end="")
                _confirm = await asyncio.get_event_loop().run_in_executor(None, input)
                _confirm = _confirm.strip().lower()

                if _confirm in ("no", "n"):
                    console.print("  [dim]Cancelled.[/dim]\n")
                    memory.add("user", query, skill="url-fetch", outcome="cancelled")
                    continue

                # Fix common command issues before executing
                _fixed_commands = []
                for _cmd in _commands:
                    # Add sudo to package managers
                    if _cmd.startswith(("pacman ", "apt ", "apt-get ", "dnf ", "yum ")):
                        _cmd = "sudo " + _cmd
                    # Fix pip --break-system-packages position
                    if "pip" in _cmd and "--break-system-packages" in _cmd:
                        # correct form: pip install --break-system-packages <pkg>
                        import re as _pre
                        _cmd = _pre.sub(
                            r"pip\s+(--break-system-packages\s+)?install\s+(--break-system-packages\s+)?",
                            "pip install --break-system-packages ",
                            _cmd
                        )
                    # Fix python -m pip --break-system-packages
                    if "python -m pip" in _cmd and "--break-system-packages" in _cmd:
                        _cmd = _cmd.replace("python -m pip --break-system-packages install", "pip install --break-system-packages")
                        _cmd = _cmd.replace("python -m pip install --break-system-packages", "pip install --break-system-packages")
                    _fixed_commands.append(_cmd)
                _commands = _fixed_commands

                # Step 4: Execute commands
                _shell3 = ShellExecutor(console)
                _failed = False
                for _ci, _cmd in enumerate(_commands, 1):
                    console.print(f"\n  [bold #f59e0b]Step {_ci}/{len(_commands)}:[/bold #f59e0b] [#5eead4]{_cmd}[/#5eead4]")

                    # Handle cd specially — can't run in subprocess
                    if _cmd.startswith("cd "):
                        import os as _os
                        _dir = _cmd[3:].strip()
                        try:
                            _os.chdir(_dir)
                            console.print(f"  [#10b981]✓ Changed to {_os.getcwd()}[/#10b981]")
                        except Exception as _cde:
                            console.print(f"  [#ef4444]✗ cd failed: {_cde}[/#ef4444]")
                        continue

                    # Handle source specially
                    if _cmd.startswith("source "):
                        _src = _cmd[7:].strip()
                        console.print(f"  [dim]Note: run 'source {_src}' manually in your shell after this.[/dim]")
                        continue

                    # Verify git clone URLs exist before running
                    if _cmd.startswith("git clone "):
                        import re as _gcre
                        _repo_url = _gcre.search(r'https://github\.com/[^\s]+', _cmd)
                        if _repo_url:
                            _ru = _repo_url.group(0).rstrip('/')
                            _check = await _asyncio2.create_subprocess_shell(
                                f"curl -s -o /dev/null -w '%{{http_code}}' {_ru}",
                                stdout=_asyncio2.subprocess.PIPE,
                                stderr=_asyncio2.subprocess.PIPE,
                            )
                            _cout, _ = await _asyncio2.wait_for(_check.communicate(), timeout=10)
                            _status = _cout.decode().strip()
                            if _status == "404":
                                console.print(f"  [yellow]⚠ Repo not found: {_ru}[/yellow]")
                                console.print(f"  [dim]Searching for correct repo...[/dim]")
                                _repo_name = _ru.split("/")[-1]
                                _search = await _asyncio2.create_subprocess_shell(
                                    f"curl -s 'https://api.github.com/search/repositories?q={_repo_name}&sort=stars' | python3 -c \"import json,sys; r=json.load(sys.stdin); [print(i['clone_url'], i['stargazers_count'], 'stars') for i in r.get('items',[])[:3]]\"",
                                    stdout=_asyncio2.subprocess.PIPE,
                                    stderr=_asyncio2.subprocess.PIPE,
                                )
                                _sout, _ = await _asyncio2.wait_for(_search.communicate(), timeout=15)
                                _suggestions = _sout.decode().strip()
                                if _suggestions:
                                    console.print(f"  [#5eead4]Alternatives found:[/#5eead4]\n{_suggestions}")
                                console.print(f"  [dim]Skipping bad clone URL.[/dim]\n")
                                continue
                    _result = await _shell3.execute("!" + _cmd, timeout=120)
                    if not _result.success and _result.returncode not in (0, None):
                        console.print(f"  [#ef4444]✗ Step {_ci} failed (exit {_result.returncode})[/#ef4444]")
                        console.print("  [bold #f59e0b]Continue anyway? (yes/no):[/bold #f59e0b] ", end="")
                        _cont = await asyncio.get_event_loop().run_in_executor(None, input)
                        if _cont.strip().lower() in ("no", "n"):
                            _failed = True
                            break

                if not _failed:
                    console.print(f"\n  [bold #10b981]✓ All {len(_commands)} steps completed![/bold #10b981]\n")
                memory.add("user", query, skill="url-fetch", outcome="executed")

            except Exception as _fe:
                console.print(f"  [dim]Error: {_fe}[/dim]\n")
            continue

        # ── RAW SHELL BYPASS ──────────────────────────────────

        # ── TARGET CONTEXT ────────────────────────────────────
        import re as _re
        _tctx = get_target_context()
        _dm = _re.search(
            r"\b([\w\-]+\.(?:com|org|net|io|co|app|dev|gov|edu|uk|de|fr))\b",
            query
        )
        if _dm and "example.com" not in _dm.group(1):
            _tctx.set_target(_dm.group(1))
        if query.lower().startswith("target "):
            _nt = query.split(" ", 1)[1].strip()
            _tctx.set_target(_nt)
            console.print(f"  [bold #10b981]✓ Target set: {_nt}[/bold #10b981]\n")
            continue
        if query.lower() in ("target", "show target"):
            console.print(f"  {_tctx.show()}\n")
            continue
        query = _tctx.inject_into_query(query)

        with console.status("[dim]  thinking...[/dim]",spinner="dots"):
            try: cls=await brain.classify(query); hint=cls.get("category_hint","general")
            except: hint="general"
            match=router.route(query,category_hint=hint)

        # Workflow
        wf=detect_workflow(query,workflows)
        if wf:
            show_wf_start(wf); carry=""
            for i,step in enumerate(wf["steps"],1):
                sname=step.get("skill",""); label=step.get("label",sname)
                show_step(i,len(wf["steps"]),label,sname)
                skill={"name":sname,"timeout":60,"requires":[],"dangerous":False}
                q_ctx=query
                if carry: q_ctx+=f"\n\nPrevious step:\n{carry[:1500]}"
                msgs=build_messages(q_ctx,memory,persona,skill=skill,settings=settings,
                                   workflow_step=label,step_number=i,total_steps=len(wf["steps"]))
                t0=time.time(); out=await stream_to_terminal(msgs,brain)
                # Hallucination guard
                _validated=safe_llm_response(out)
                if _validated != out:
                    console.print(f"\n  [bold #f59e0b]{_validated}[/bold #f59e0b]\n")
                    out=_validated
                ms=int((time.time()-t0)*1000); carry=out; show_step_done(True,label,ms)
            console.print(f"\n  [bold #10b981]✓ Workflow complete[/bold #10b981]\n")
            last_output=carry; last_skill=wf["name"]
            memory.add("user",query,skill=wf["name"],outcome="workflow_complete"); continue

        # Single skill / direct
        if match: show_skill_match(match)
        else: console.print("  [dim]no match — answering directly[/dim]\n")
        msgs=build_messages(query,memory,persona,skill=match,settings=settings)
        t0=time.time(); out=await stream_to_terminal(msgs,brain)
        # Hallucination guard
        _validated=safe_llm_response(out)
        if _validated != out:
            console.print(f"\n  [bold #f59e0b]{_validated}[/bold #f59e0b]\n")
            out=_validated
        ms=int((time.time()-t0)*1000)
        last_output=out; last_skill=match["name"] if match else None
        console.print(f"\n  [dim]{ms}ms{'  ·  '+match['name'] if match else ''}[/dim]\n")
        memory.add("user",query,skill=match["name"] if match else None,outcome="success")
        memory.add("assistant",out)

if __name__=="__main__":
    try: asyncio.run(main_loop())
    except KeyboardInterrupt: console.print("\n  [dim]interrupted.[/dim]\n"); sys.exit(0)

# ═══════════════════════════════════════════════════
# JARVIS BUG FIXES — appended patch
# Apply at bottom of main_loop() dispatch chain
# ═══════════════════════════════════════════════════
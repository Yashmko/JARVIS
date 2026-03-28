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
from tools.multi_agent import MultiAgent, is_multi_command
from tools.browser_auto import BrowserAutomation, is_browser_command
from tools.autonomous import AutonomousAgent, is_auto_command

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
        if is_local_command(query):
            console.print(); result=await local_tools.execute(query)
            if result.error: console.print(Text(f"\n  ✗ {result.error}\n",style="bold #ef4444"))
            memory.add("user",query,skill="local-tools",outcome="success" if result.success else "error"); continue

        # Classify + route
        console.print()
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
                ms=int((time.time()-t0)*1000); carry=out; show_step_done(True,label,ms)
            console.print(f"\n  [bold #10b981]✓ Workflow complete[/bold #10b981]\n")
            last_output=carry; last_skill=wf["name"]
            memory.add("user",query,skill=wf["name"],outcome="workflow_complete"); continue

        # Single skill / direct
        if match: show_skill_match(match)
        else: console.print("  [dim]no match — answering directly[/dim]\n")
        msgs=build_messages(query,memory,persona,skill=match,settings=settings)
        t0=time.time(); out=await stream_to_terminal(msgs,brain)
        ms=int((time.time()-t0)*1000)
        last_output=out; last_skill=match["name"] if match else None
        console.print(f"\n  [dim]{ms}ms{'  ·  '+match['name'] if match else ''}[/dim]\n")
        memory.add("user",query,skill=match["name"] if match else None,outcome="success")
        memory.add("assistant",out)

if __name__=="__main__":
    try: asyncio.run(main_loop())
    except KeyboardInterrupt: console.print("\n  [dim]interrupted.[/dim]\n"); sys.exit(0)

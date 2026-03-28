# JARVIS v2 — Autonomous AI Agent OS



```bash
cd ~/jarvis
cat > README.md << 'READMEEOF'
<div align="center">

```
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
```

**An autonomous AI agent OS that runs on 1.2GB RAM.**

[![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white)](https://python.org)
[![Skills](https://img.shields.io/badge/Skills-1,320-purple)](.)
[![LLMs](https://img.shields.io/badge/LLM_Providers-7_Free-green)](.)
[![RAM](https://img.shields.io/badge/RAM-72MB-orange)](.)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>

---

## The Engineering Challenge

**The constraint:** Build a fully autonomous AI agent on a machine with 1.7GB total RAM (1.2GB usable after Arch Linux + i3), an Intel Pentium B970, no GPU, and zero budget for API costs.

**The result:** An agent OS that classifies queries in 180ms, routes to the best skill out of 1,320 in <1ms, streams responses through 7 free LLM providers with automatic failover, and remembers everything — using 72MB of RAM.

```
┌─────────────────────────────────────────────────────────┐
│  AVAILABLE                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ 1.2GB    │ │ Pentium  │ │ No GPU   │ │ $0 budget │  │
│  │ usable   │ │ B970     │ │          │ │           │  │
│  │ RAM      │ │ 2.3GHz   │ │          │ │           │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
│                                                         │
│  BUILT                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ 1,320    │ │ 7 LLM    │ │ 72MB     │ │ Autonomous│  │
│  │ skills   │ │ providers│ │ RAM used │ │ execution │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Key Engineering Decisions

Every constraint forced a design choice. Every choice has a reason.

### 1. Why TF-IDF instead of embeddings?

| Approach | RAM | Speed | Accuracy |
|----------|-----|-------|----------|
| sentence-transformers + FAISS | 1.4GB | 2ms | ~95% |
| **TF-IDF + fuzzy matching** | **40MB** | **<1ms** | **~85%** |

Embedding models need PyTorch (1.4GB). That alone exceeds our total RAM. TF-IDF with Levenshtein fuzzy matching and phrase weighting gets 85% accuracy at 35x less memory. The 10% accuracy gap is covered by 79 alias shortcuts for common queries.

### 2. Why 7 free providers instead of one paid API?

```
Request ──► Groq ──✗──► Cerebras ──✗──► Gemini ──✓──► Response
            │              │               │
         rate limit      503 error      success
```

Any single free provider has rate limits and downtime. With 7 providers in a fallback chain, the probability of all 7 failing simultaneously is near zero. One `openai` library handles all 7 — they all expose OpenAI-compatible endpoints.

**Cost comparison:**
| Approach | Monthly Cost |
|----------|-------------|
| ChatGPT Plus | $20 |
| Claude Pro | $20 |
| GPT-4 API (moderate use) | $30-100 |
| **JARVIS (7 free providers)** | **$0** |

### 3. Why SQLite WAL instead of Redis/PostgreSQL?

| Database | RAM overhead | Setup | Persistence |
|----------|-------------|-------|-------------|
| Redis | 50-100MB | Requires daemon | In-memory (volatile) |
| PostgreSQL | 30-80MB | Complex setup | Full |
| **SQLite WAL** | **<1MB** | **Zero config** | **Full** |

SQLite with Write-Ahead Logging gives concurrent reads without locks, uses negligible RAM, and persists to a single file. Combined with indexed columns and auto-compression every 100 episodes, it handles the entire memory system in under 1MB overhead.

### 4. Why curl-based scraping instead of Selenium?

| Tool | RAM | Dependencies | Speed |
|------|-----|-------------|-------|
| Selenium + Chrome | 300-500MB | Chrome, chromedriver | Slow |
| Playwright | 200-400MB | Browser binaries | Medium |
| **curl + regex** | **<1MB** | **Pre-installed** | **Fast** |

The target machine can't afford 300MB for a headless browser. curl is pre-installed on every Linux system, handles redirects, custom headers, and timeouts. Python regex extracts links, emails, and tech signatures from the HTML. Same results, 300x less RAM.

### 5. Why action mode by default?

Most AI assistants respond to "scan my website" with "Sure! What's the URL? What type of scan? What's your scope?" — 5 questions before doing anything.

JARVIS injects this into every system prompt:
```
- NEVER ask the user for more information
- NEVER say 'please provide' or 'I need'
- Make reasonable assumptions and EXECUTE
- You are the expert — DECIDE and DELIVER
```

Result: you say "scan my website for vulnerabilities" and get actual results, not a questionnaire.

---

## How It Works

```
                        "find XSS on my website"
                                  │
                    ┌─────────────┴─────────────┐
                    │      brain.classify()      │
                    │  Groq 8B instant (180ms)   │
                    │  → category: security      │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │      router.route()        │
                    │  TF-IDF + fuzzy (<1ms)     │
                    │  1,320 skills searched     │
                    │  → vulnerability-scanner   │
                    │  → confidence: 99%         │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │  context_injector.build()  │
                    │  ┌─────────────────────┐   │
                    │  │ Persona (identity)  │   │
                    │  │ Mode (act/concise)  │   │
                    │  │ Pins (your context) │   │
                    │  │ Memory (past tasks) │   │
                    │  │ SKILL.md (expert)   │   │
                    │  │ User query          │   │
                    │  └─────────────────────┘   │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │     brain.stream()         │
                    │  Groq → Cerebras → Gemini  │
                    │  → Together → Mistral      │
                    │  → OpenRouter → HuggingFace│
                    │  (first available wins)    │
                    └─────────────┬─────────────┘
                                  │
                         live token stream
                                  │
                    ┌─────────────┴─────────────┐
                    │      memory.add()          │
                    │  Tier 1: deque (20 turns)  │
                    │  Tier 2: SQLite (forever)  │
                    │  Stats: skill usage track  │
                    └───────────────────────────┘
```

---

## Capability Map

```
┌──────────────────────────────────────────────────────────────┐
│                      JARVIS v2                               │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│   🧠 THINK    │   ⚡ ACT      │   💾 REMEMBER │   🔌 EXTEND     │
├──────────────┼──────────────┼──────────────┼─────────────────┤
│ 7 LLMs       │ System ctrl  │ 3-tier memory│ Plugin system   │
│ 1,320 skills │ File ops     │ WAL SQLite   │ Custom workflows│
│ Fuzzy router │ Shell exec   │ Profiles     │ Telegram bot    │
│ Classify     │ Bug bounty   │ Context pins │ Web UI          │
│ Multi-agent  │ Browser auto │ Auto-compress│ MCP server      │
│ Action mode  │ Git control  │ Stats track  │ Skill creator   │
│ 5 modes      │ Autonomous   │ Export/backup│ Auto-improve    │
│ 8 profiles   │ Queue/cron   │ Recall search│ Report gen      │
└──────────────┴──────────────┴──────────────┴─────────────────┘
```

---

## Memory Architecture

The three tiers solve different problems at different costs:

```
┌─────────────────────────────────────────────────────────────┐
│ TIER 1: SHORT-TERM                                          │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ deque(maxlen=20)                                        │ │
│ │ Last 20 conversation turns                              │ │
│ │ Injected verbatim into every LLM call                   │ │
│ │ Cost: ~0 RAM │ Speed: O(1) │ Persistence: session only  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                           │                                 │
│ TIER 2: EPISODIC                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ SQLite WAL with indexes                                 │ │
│ │ Every task, skill, outcome, timestamp, profile          │ │
│ │ Keyword recall with relevance scoring                   │ │
│ │ Auto-compressed every 100 episodes                      │ │
│ │ Cost: <1MB │ Speed: <5ms │ Persistence: forever         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                           │                                 │
│ STATS LAYER                                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Per-skill: usage count, success rate                    │ │
│ │ Per-provider: token count from usage.log                │ │
│ │ Per-route: confidence scores from router.log            │ │
│ │ Used by: dashboard, auto-improve, self-learning         │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow Engine

Workflows chain skills with context handoff. Each step receives the previous step's output and unique instructions that prevent repetition.

```
"security audit"
     │
     ▼
┌──────────────┐     ┌──────────┐     ┌──────────┐
│ 1.Methodology│────►│ 2. Scan  │────►│ 3. Web   │
│  [██░░░░]    │     │ [███░░░] │     │ [████░░] │
│              │     │          │     │          │
│ "Outline the │     │"Execute  │     │"Test XSS,│
│  approach"   │     │ the scan,│     │ CSRF,    │
│              │     │ show CVEs│     │ SSRF"    │
└──────────────┘     └──────────┘     └──────────┘
                                           │
     ┌─────────────────────────────────────┘
     ▼
┌──────────────┐     ┌──────────┐     ┌──────────┐
│ 4. API       │────►│ 5.PrivEsc│────►│ 6.Report │
│ [█████░]     │     │ [██████] │     │ [███████]│
│              │     │          │     │          │
│"Test auth    │     │"Check    │     │"Write    │
│ bypass, IDOR"│     │ SUID,    │     │ executive│
│              │     │ cron"    │     │ summary" │
└──────────────┘     └──────────┘     └──────────┘
```

**Why each step produces unique output:**

The context injector adds step-specific instructions:
```python
STEP_PROMPTS = {
    "Methodology": "Outline the specific methodology. List exact steps.",
    "Scan":        "Execute the scan. Show findings with severity ratings.",
    "Web layer":   "Test XSS, CSRF, SSRF. Show payloads and results.",
    "API security":"Test auth bypass, IDOR, rate limiting. Show examples.",
    "Final report":"Write executive summary. Findings sorted by severity.",
}
```

Combined with: *"You are executing step 3 of 6. Do NOT repeat previous steps. Produce UNIQUE output for THIS step only."*

---

## Autonomous Execution Loop

When you say `auto: scan localhost for vulnerabilities`, JARVIS doesn't just generate text. It executes real commands:

```
┌──────────────────────────────────────────────────────┐
│                 AUTONOMOUS LOOP                       │
│                                                      │
│  ┌─────────┐     ┌──────────┐     ┌──────────────┐  │
│  │  BRAIN   │────►│ COMMAND  │────►│   EXECUTE    │  │
│  │ "What    │     │ "nmap    │     │ subprocess   │  │
│  │  next?"  │     │  -sT     │     │ async shell  │  │
│  └────▲─────┘     │  localhost│     └──────┬───────┘  │
│       │           └──────────┘            │          │
│       │                                   │          │
│       │           ┌──────────┐            │          │
│       └───────────│ ANALYZE  │◄───────────┘          │
│                   │ output   │                       │
│                   │ → decide │                       │
│                   │   next   │                       │
│                   └──────────┘                       │
│                                                      │
│  Safety: ⛔ rm, dd, mkfs, shutdown → BLOCKED         │
│  Limit:  🔄 Max 10 iterations                        │
│  Confirm: ⚠ "Type yes to proceed"                    │
└──────────────────────────────────────────────────────┘
```

---

## Bug Bounty Pipeline

```
bounty workflow example.com
            │
            ├──► 🔍 Subdomain Enumeration
            │    │  Source: crt.sh certificate transparency
            │    │  Method: curl → JSON parse → deduplicate
            │    └── Result: 318 unique subdomains
            │         └── Saved: reports/example.com_subdomains.txt
            │
            ├──► 🛡️ Security Header Analysis
            │    │  Checks: HSTS, CSP, X-Frame, X-Content-Type,
            │    │          X-XSS, Referrer-Policy, Permissions-Policy
            │    │  Method: curl -I → parse → severity rating
            │    └── Result: 6 missing headers (1 critical, 1 high)
            │         └── Finding: ✗ HSTS missing (critical)
            │
            ├──► 🔧 Tech Stack Fingerprinting
            │    │  Signatures: 23+ technologies
            │    │  Checks: HTML source + response headers
            │    └── Result: React, Next.js, Cloudflare, Stripe
            │
            ├──► 🚪 Port Scanning
            │    │  Method: nmap (if installed) or bash /dev/tcp
            │    │  Ports: top 100 (nmap) or 24 common (fallback)
            │    └── Result: 80, 443, 22 open
            │
            ├──► 🧠 AI Analysis
            │    │  Feed all findings to LLM
            │    │  Rate severity, suggest exploitation paths
            │    └── Estimate bounty value per finding
            │
            └──► 📄 Report Generation
                 ├── Markdown: reports/bounty_report_example.com.md
                 ├── JSON:     reports/bounty_report_example.com.json
                 └── Contents: Executive summary, findings by severity,
                               reproduction steps, remediation advice
```

---

## Performance Profile

| Operation | Time | RAM Cost | Method |
|-----------|------|----------|--------|
| Boot & load 1,320 skills | 2.1s | +45MB | TF-IDF index build |
| Classify query | 180ms | 0 | Groq Llama 8B API |
| Route to skill | 0.3ms | 0 | In-memory TF-IDF |
| Build context | <1ms | 0 | String concat |
| Stream first token | 400ms | 0 | Provider dependent |
| Memory recall | 3ms | 0 | SQLite indexed query |
| Memory write | <1ms | 0 | SQLite WAL |
| Full recon scan | 15-30s | +2MB | curl subprocesses |
| Report generation | <1ms | 0 | String template |
| **Total idle RAM** | — | **72MB** | Measured via /proc |

**RAM breakdown:**
```
Python interpreter     30MB  ████████░░░░░░░░░░░░
Loaded modules         22MB  █████░░░░░░░░░░░░░░░
TF-IDF index (1,320)   15MB  ███░░░░░░░░░░░░░░░░░
SQLite + deque          3MB  █░░░░░░░░░░░░░░░░░░░
Rich terminal           2MB  ░░░░░░░░░░░░░░░░░░░░
────────────────────────────
Total                  72MB  ████████████████░░░░  (of 1,200MB available)
Free for user         ~800MB ░░░░░░░░░░░░░░░░████████████████████
```

---

## Project Structure

```
jarvis/
│
├── main.py                    ← Entry point: REPL, command dispatch, UI
├── brain.py                   ← 7-provider LLM with fallback chain
├── router.py                  ← TF-IDF fuzzy router over 1,320 skills
├── executor.py                ← Sandboxed execution with timeout/retry
├── context_injector.py        ← Assembles LLM context (persona+memory+skill+pins+mode)
│
├── config/
│   ├── settings.py            ← Single source of truth for all config
│   ├── profiles.py            ← 8 startup profiles with persona overrides
│   ├── persona.md             ← JARVIS identity prompt
│   └── aliases.json           ← 79 shortcut → skill mappings
│
├── memory/
│   └── memory.py              ← 3-tier: deque + SQLite WAL + stats + pins + KV store
│
├── tools/
│   ├── bounty.py              ← Bug bounty: recon, headers, tech, ports, nuclei, reports
│   ├── autonomous.py          ← Self-executing agent loop (plan → run → analyze → repeat)
│   ├── multi_agent.py         ← Task decomposition into parallel sub-agents
│   ├── system_control.py      ← OS control: apps, commands, volume, screenshot
│   ├── local_tools.py         ← File ops: read, write, find, search, tree, diff, zip
│   ├── browser_auto.py        ← Scrape, monitor, download (curl-based, no Selenium)
│   ├── automation.py          ← Queue, cron, git, clipboard, skill chains
│   ├── skill_creator.py       ← Self-learning: generate + score + save new skills
│   ├── plugin_loader.py       ← Auto-load .py plugins from plugins/
│   ├── dashboard.py           ← Rich visual stats dashboard
│   ├── report_gen.py          ← Export: markdown, JSON reports
│   ├── maintenance.py         ← Backup, vacuum, cache clear, log trim
│   ├── auto_improve.py        ← Read router.log → fix skill triggers with AI
│   ├── telegram_bot.py        ← Telegram bot for remote control
│   └── gen_manifests.py       ← Generate manifest.json for all skills
│
├── api/
│   ├── server.py              ← FastAPI + WebSocket (web UI backend)
│   ├── mcp.py                 ← MCP server for Claude Desktop / Cursor / VSCode
│   └── static/index.html      ← Dark-mode web chat UI
│
├── workflows/                 ← JSON workflow definitions
│   ├── security_audit.json    ← 6-step: methodology → scan → web → API → privesc → report
│   ├── saas_mvp.json          ← 7-step: idea → plan → arch → frontend → API → tests → PR
│   ├── build_ai_agent.json    ← 6-step: idea → design → RAG → graph → prompts → tests
│   ├── debug_and_fix.json     ← 4-step: diagnose → strategy → validate → submit
│   ├── deploy_cloud.json      ← 4-step: containerise → AWS → deploy → monitor
│   └── bug_bounty.json        ← 6-step: methodology → scan → web → SQLi → API → report
│
├── plugins/                   ← Drop .py files here, auto-loaded on startup
│   ├── hello.py               ← Example: greeting plugin
│   ├── weather.py             ← Example: weather via wttr.in
│   └── timer.py               ← Example: countdown timer
│
└── skills/                    ← 1,320 skill folders (cloned from Antigravity repo)
    ├── vulnerability-scanner/
    │   ├── SKILL.md            ← Expert instructions injected into LLM context
    │   └── manifest.json       ← Name, category, triggers, tags, timeout
    ├── react-best-practices/
    ├── ethical-hacking-methodology/
    └── ... (1,317 more)
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/JARVIS.git
cd JARVIS

# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install openai rich python-dotenv aiofiles fastapi uvicorn

# Skills (1,320 specialist skill packs)
git clone --depth=1 https://github.com/sickn33/antigravity-awesome-skills.git _tmp
mkdir -p skills && cp -r _tmp/skills/* skills/ 2>/dev/null && cp -r _tmp/* skills/ 2>/dev/null && rm -rf _tmp
python3 tools/gen_manifests.py --force

# API keys (all free — pick at least one)
cp .env.example .env && nano .env

# Launch
python3 main.py
```

**Startup profiles:**
```bash
python3 main.py --bugbounty     # 💰 Bug bounty hunting mode
python3 main.py --coding        # 💻 Code-focused mode
python3 main.py --lite          # ⚡ Fast, minimal output
python3 main.py --safe          # 🔒 No dangerous commands
python3 main.py --automation    # 🤖 Task automation mode
```

**Additional interfaces:**
```bash
uvicorn api.server:app --port 8000     # Web UI → localhost:8000
python3 api/mcp.py                      # MCP server → Claude/Cursor/VSCode
python3 tools/telegram_bot.py           # Telegram bot → control from phone
```

---

## Tech Stack & Why

| Layer | Choice | Why Not the Alternative |
|-------|--------|----------------------|
| Language | Python 3.14 + AsyncIO | Need async for concurrent LLM streams |
| LLM API | `openai` library | Handles all 7 providers — one library, zero vendor lock |
| Routing | Custom TF-IDF | PyTorch embeddings need 1.4GB — more than total RAM |
| Database | SQLite WAL | Redis needs a daemon, Postgres needs setup, SQLite is zero-config |
| Terminal | Rich | Best Python TUI library, tables + panels + colors |
| Web | FastAPI + WebSocket | Lightweight, async-native, WebSocket for streaming |
| Scraping | curl + regex | Selenium needs 300MB+ for headless Chrome |
| Notifications | notify-send | Native Linux, zero overhead |
| Bot | python-telegram-bot | Free, simple, works on any phone |

---

## Self-Improvement Loop

JARVIS gets better the more you use it:

```
┌──────────────────────────────────────────────────┐
│                                                  │
│   USE JARVIS ──► router.log records every route  │
│       │                                          │
│       ▼                                          │
│   "improve routing" ──► auto_improve.py reads    │
│       │                  low-confidence routes    │
│       ▼                                          │
│   Brain suggests ──► better triggers added to    │
│       │               manifest.json              │
│       ▼                                          │
│   Next query ──► higher confidence routing       │
│       │                                          │
│       └──────────────────────────────────────────┘
│                  (continuous loop)
└──────────────────────────────────────────────────┘
```

**Skill creation loop:**
```
You: "create a skill for Docker security auditing"
  │
  ├── Brain generates SKILL.md (expert instructions)
  ├── Quality scorer rates it (0-100, 5 dimensions)
  │   ├── Length (20pts)
  │   ├── Title/structure (18pts)
  │   ├── Action verbs (20pts)
  │   ├── Headers/bullets (20pts)
  │   └── Name relevance (20pts)
  ├── If score < 60: brain rewrites until passing
  ├── Manifest generated with triggers
  └── Skill immediately routable
```

---

## License

MIT — use it, modify it, sell it, build on it. No restrictions.

---

<div align="center">

**Built on a $50 laptop. Zero paid APIs. 72MB RAM. 1,320 skills. Fully autonomous.**

*The best engineering isn't about having the most resources — it's about building the most with the least.*

</div>
READMEEOF
```

Now commit and push:

```bash
cd ~/jarvis
git add -A
git commit -m "Professional README with architecture diagrams and engineering decisions"
git push
```

Replace `YOUR_USERNAME` in the README with your actual GitHub username:

```bash
sed -i 's/YOUR_USERNAME/PUT_YOUR_ACTUAL_USERNAME_HERE/g' README.md
git add README.md
git commit -m "Updated GitHub username in README"
git push
```

Replace `PUT_YOUR_ACTUAL_USERNAME_HERE` with your real username in that command.

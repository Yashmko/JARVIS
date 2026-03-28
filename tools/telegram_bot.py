"""
JARVIS v2 — tools/telegram_bot.py

Control Jarvis from your phone via Telegram.

Setup:
1. Message @BotFather on Telegram
2. Send /newbot → name it "Jarvis" → get token
3. Add token to .env: TELEGRAM_BOT_TOKEN=your_token
4. Run: python tools/telegram_bot.py
5. Message your bot from your phone

Commands work the same as terminal:
  scan my website
  bounty recon example.com
  skills search hacking
  sysinfo
  stats
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USERS = os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")


async def main():
    if not TOKEN:
        print("\n  Telegram Bot Setup:")
        print("  1. Message @BotFather on Telegram")
        print("  2. Send /newbot")
        print("  3. Copy the token")
        print("  4. Add to .env: TELEGRAM_BOT_TOKEN=your_token_here")
        print("  5. Optionally: TELEGRAM_ALLOWED_USERS=your_user_id")
        print("  6. Run again: python tools/telegram_bot.py\n")
        return

    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    from config.settings import Settings
    from brain import BrainClient
    from router import Router
    from memory.memory import Memory
    from context_injector import build_messages
    from tools.bounty import BountyToolkit, is_bounty_command
    from tools.system_control import SystemController, is_sys_command

    settings = Settings()
    brain = BrainClient(settings)
    router = Router(settings)
    memory = Memory(window=10, db_path=settings.MEMORY_DB, profile="telegram")

    from rich.console import Console
    tg_console = Console(force_terminal=False, no_color=True)
    bounty = BountyToolkit(tg_console, brain=brain)
    sys_ctrl = SystemController(tg_console)

    print(f"\n  🤖 Jarvis Telegram Bot starting...")
    print(f"  Skills: {len(router.skills)}")
    print(f"  Waiting for messages...\n")

    async def start(update: Update, context):
        await update.message.reply_text(
            "🟢 Jarvis online.\n\n"
            f"Skills: {len(router.skills)}\n"
            "Providers: 7 LLMs\n\n"
            "Commands:\n"
            "/help - Show commands\n"
            "/skills - List skills\n"
            "/stats - Usage stats\n"
            "/bounty - Bug bounty tools\n\n"
            "Or just type naturally — I'll route to the right skill."
        )

    async def help_cmd(update: Update, context):
        await update.message.reply_text(
            "📋 Commands:\n\n"
            "Just type naturally:\n"
            "  scan my API for vulnerabilities\n"
            "  debug my python code\n"
            "  brainstorm startup ideas\n\n"
            "Bug Bounty:\n"
            "  bounty recon example.com\n"
            "  bounty headers example.com\n"
            "  bounty subdomains example.com\n\n"
            "System:\n"
            "  /skills - List skills\n"
            "  /stats - Usage dashboard\n"
            "  /sysinfo - System info\n"
            "  sysinfo - Same thing\n"
        )

    async def skills_cmd(update: Update, context):
        cats = router.get_categories()
        text = "📚 Skills by category:\n\n"
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            text += f"  {cat}: {count}\n"
        text += f"\nTotal: {len(router.skills)}"
        await update.message.reply_text(text)

    async def stats_cmd(update: Update, context):
        s = memory.get_stats()
        text = (
            f"📊 Dashboard:\n\n"
            f"Profile: {s['profile']}\n"
            f"Tasks: {s['total']} ({s['total_all']} total)\n"
            f"Tokens: {s['total_tokens']:,}\n"
            f"RAM: {s['ram_mb']}MB\n"
            f"DB: {s['db_size_mb']}MB\n"
        )
        if s['providers']:
            text += "\nProviders:\n"
            for p, t in sorted(s['providers'].items(), key=lambda x: -x[1]):
                text += f"  {p}: {t:,} tokens\n"
        await update.message.reply_text(text)

    async def handle_message(update: Update, context):
        query = update.message.text.strip()
        user_id = str(update.effective_user.id)

        # Optional: restrict to allowed users
        if ALLOWED_USERS and ALLOWED_USERS[0] and user_id not in ALLOWED_USERS:
            await update.message.reply_text("⛔ Not authorized. Add your user ID to TELEGRAM_ALLOWED_USERS in .env")
            return

        if not query:
            return

        # Send "typing" indicator
        await update.message.chat.send_action("typing")

        try:
            # Check for special commands
            if is_bounty_command(query):
                result = await bounty.execute(query)
                response = result.output[:4000] if result.output else result.error
                await update.message.reply_text(f"🔍 {response}")
                memory.add("user", query, skill="bounty-toolkit",
                          outcome="success" if result.success else "error")
                return

            if query.lower() in ("sysinfo", "system info"):
                result = sys_ctrl.system_info()
                await update.message.reply_text(f"💻 {result.output[:4000]}")
                return

            # Regular query — classify, route, execute
            try:
                cls = await brain.classify(query)
                hint = cls.get("category_hint", "general")
            except Exception:
                hint = "general"

            match = router.route(query, category_hint=hint)

            skill_info = ""
            if match:
                skill_info = f"⚡ {match['name']} [{match.get('category','')}] {match.get('score',0):.0%}\n\n"

            msgs = build_messages(query, memory, settings.PERSONA,
                                 skill=match, settings=settings)

            # Collect response (no streaming in Telegram)
            response = ""
            async for token in brain.stream(msgs):
                response += token

            # Truncate for Telegram (4096 char limit)
            if len(response) > 3900:
                response = response[:3900] + "\n\n... (truncated)"

            await update.message.reply_text(skill_info + response)

            memory.add("user", query, skill=match["name"] if match else None, outcome="success")
            memory.add("assistant", response)

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:500]}")

    # Build app
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("skills", skills_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("  ✓ Bot running. Send a message to your Telegram bot.\n")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())

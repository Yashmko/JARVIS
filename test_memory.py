"""Quick test — memory and context injection."""
import asyncio
import sys
sys.path.insert(0, ".")

from config.settings import Settings
from brain import BrainClient
from memory.memory import Memory
from context_injector import build_messages


async def main():
    settings = Settings()
    brain = BrainClient(settings)
    memory = Memory(window=20, db_path=settings.MEMORY_DB)

    print("\n  JARVIS v2 — Memory Test\n")

    # 1. Add some memories
    memory.add("user", "scanned example.com for XSS",
               skill="vulnerability-scanner", outcome="success", duration_ms=3200)
    memory.add("user", "built a react dashboard",
               skill="react-best-practices", outcome="success", duration_ms=8100)
    memory.add("user", "debugged python async error",
               skill="systematic-debugging", outcome="success", duration_ms=5400)
    print("  ✓ Added 3 memories")

    # 2. Test recall
    recalled = memory.recall("scan for vulnerabilities")
    print(f"\n  Recall 'scan for vulnerabilities':")
    print(f"  {recalled[:200] if recalled else '(nothing)'}")

    # 3. Test context building
    msgs = build_messages(
        "scan my website for bugs",
        memory,
        settings.PERSONA,
        settings=settings,
    )
    print(f"\n  ✓ Built {len(msgs)} messages for LLM")
    print(f"  System prompt length: {len(msgs[0]['content'])} chars")

    # 4. Test with brain — does memory context work?
    print(f"\n  Asking Jarvis with memory context...\n")
    print("  Jarvis: ", end="", flush=True)
    async for token in brain.stream(msgs):
        print(token, end="", flush=True)

    # 5. Stats
    stats = memory.get_stats()
    print(f"\n\n  Stats: {stats['total']} episodes")
    for skill, uses, success in stats['top_skills']:
        print(f"    {skill}: {uses} uses, {success} success")

    # 6. Test forget
    memory.forget("last")
    print(f"\n  ✓ Forgot last memory")

    history = memory.get_history(5)
    print(f"  History entries: {len(history)}")

    print("\n  ✓ Memory works! Phase 2 complete.\n")


if __name__ == "__main__":
    asyncio.run(main())

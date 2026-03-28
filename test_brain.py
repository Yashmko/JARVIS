"""Quick test — does Jarvis have a working brain?"""
import asyncio
import sys
sys.path.insert(0, ".")

from config.settings import Settings
from brain import BrainClient


async def main():
    settings = Settings()
    brain = BrainClient(settings)

    # Show which providers have keys
    print("\n  JARVIS v2 — Brain Test\n")
    for name, _, key_attr, model in settings.MODEL_CHAIN:
        key = getattr(settings, key_attr, "")
        status = "✓" if key else "✗"
        print(f"  {status} {name:<14} {model}")

    print(f"\n  Testing stream...\n")

    # Test streaming
    print("  Jarvis: ", end="", flush=True)
    async for token in brain.stream([
        {"role": "user", "content": "Say exactly: 'Jarvis online. All systems nominal.' and nothing else."}
    ]):
        print(token, end="", flush=True)

    print("\n")

    # Test classify
    print("  Testing classify...\n")
    result = await brain.classify("scan my website for vulnerabilities")
    print(f"  Classification: {result}")

    print("\n  ✓ Brain works! Phase 1 complete.\n")


if __name__ == "__main__":
    asyncio.run(main())

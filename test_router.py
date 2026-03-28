"""Quick test — does routing work?"""
import asyncio
import sys
import time
sys.path.insert(0, ".")

from config.settings import Settings
from router import Router
from brain import BrainClient


async def main():
    settings = Settings()

    print("\n  JARVIS v2 — Router Test\n")

    t0 = time.time()
    router = Router(settings)
    ms = int((time.time() - t0) * 1000)

    print(f"  ✓ Loaded {len(router.skills)} skills in {ms}ms")

    # Category breakdown
    cats = router.get_categories()
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {cat:<20} {count:>4} skills")

    # Test routing
    print(f"\n  Testing routes:\n")
    test_queries = [
        "scan for vulnerabilities",
        "build a react app",
        "debug my python code",
        "deploy to docker",
        "write unit tests",
        "design system architecture",
        "find XSS on a website",
        "create a pull request",
        "brainstorm startup ideas",
        "hack this target",
    ]

    brain = BrainClient(settings)

    for q in test_queries:
        cls = await brain.classify(q)
        hint = cls.get("category_hint", "general")
        match = router.route(q, category_hint=hint)

        if match:
            print(f"    {q:<35} -> {match['name']:<35} "
                  f"{match['score']:.0%} via:{match.get('via','?')}")
        else:
            print(f"    {q:<35} -> (no match)")

    # Test search
    print(f"\n  Search 'bug bounty hunting':")
    results = router.search_skills("bug bounty hunting", k=5)
    for r in results:
        print(f"    {r['score']:.0%}  {r['name']:<40} [{r.get('category','')}]")

    # List all skill names for alias building
    print(f"\n  All skill names (for alias building):")
    for s in router.skills:
        print(f"    {s['name']}")

    print(f"\n  ✓ Router works! Phase 3 complete.\n")


if __name__ == "__main__":
    asyncio.run(main())

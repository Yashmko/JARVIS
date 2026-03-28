"""
JARVIS v2 — tools/auto_improve.py

Reads router.log, finds low-confidence routes,
uses LLM to suggest better triggers, patches manifests.
Run: python3 tools/auto_improve.py
Or from Jarvis: "improve routing"
"""
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ROUTER_LOG = Path("memory/router.log")
SKILLS_DIR = Path("skills")
THRESHOLD = 0.60
MIN_MISSES = 2


async def main():
    print(f"\n  JARVIS Auto-Improve — {datetime.now():%Y-%m-%d %H:%M}\n")

    if not ROUTER_LOG.exists():
        print("  No router.log yet. Use Jarvis first.")
        return

    # Analyze routes
    total = 0
    misses = defaultdict(list)
    unmatched = []

    for line in ROUTER_LOG.read_text().splitlines():
        try:
            row = json.loads(line)
            total += 1
            score = row.get("score", 1.0)
            if score < THRESHOLD:
                skill = row.get("skill", "unknown")
                query = row.get("query", "")
                misses[skill].append(query)
                if score < 0.3:
                    unmatched.append(query)
        except Exception:
            pass

    print(f"  Analyzed {total} routing decisions")
    low_conf = {k: v for k, v in misses.items() if len(v) >= MIN_MISSES}
    print(f"  Low-confidence skills: {len(low_conf)}")
    print(f"  Unmatched queries: {len(unmatched)}")

    if not low_conf and not unmatched:
        print("  ✓ Routing looks good — nothing to improve.")
        return

    # Show what needs fixing
    print(f"\n  Skills needing better triggers:\n")
    for skill, queries in sorted(low_conf.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"    {skill} ({len(queries)} low-conf queries)")
        for q in queries[:3]:
            print(f"      → \"{q}\"")

    if unmatched:
        print(f"\n  Unmatched queries (no skill found):\n")
        for q in unmatched[:10]:
            print(f"    → \"{q}\"")

    # Use LLM to suggest improvements
    from config.settings import Settings
    from brain import BrainClient

    settings = Settings()
    brain = BrainClient(settings)

    improved = 0
    for skill_name, queries in list(low_conf.items())[:10]:
        mf_path = SKILLS_DIR / skill_name / "manifest.json"
        if not mf_path.exists():
            continue

        manifest = json.loads(mf_path.read_text())

        prompt = [{
            "role": "system",
            "content": "Improve skill routing. Respond ONLY with JSON: {\"new_triggers\": [\"word1\", \"word2\", ...]}"
        }, {
            "role": "user",
            "content": (
                f"Skill: {skill_name}\n"
                f"Current triggers: {manifest.get('triggers', [])}\n"
                f"Queries that should match but scored low:\n" +
                "\n".join(f"  - {q}" for q in queries[:5])
            )
        }]

        print(f"\n  Improving {skill_name}...", end=" ", flush=True)

        try:
            resp = await brain.complete(prompt)
            clean = resp.strip().strip("`").strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()
            sugg = json.loads(clean)

            if sugg.get("new_triggers"):
                old_triggers = manifest.get("triggers", [])
                new_triggers = list(dict.fromkeys(old_triggers + sugg["new_triggers"]))[:20]
                manifest["triggers"] = new_triggers
                mf_path.write_text(json.dumps(manifest, indent=2))
                print(f"✓ Added {len(sugg['new_triggers'])} triggers")
                improved += 1
            else:
                print("(no suggestions)")
        except Exception as e:
            print(f"✗ {e}")

    print(f"\n  ✓ Done. {improved} skills improved.")
    if improved > 0:
        print("  Restart Jarvis to load updated manifests.\n")


if __name__ == "__main__":
    asyncio.run(main())

"""
JARVIS v2 — tools/gen_manifests.py

Generates manifest.json for every skill folder.
Run once after cloning skills.
"""
import json
import re
import sys
from pathlib import Path

SKILLS_DIR = Path("skills")

CATEGORY_RULES = [
    ("security", ["security", "hack", "pentest", "vuln", "owasp", "exploit",
                  "injection", "burp", "metasploit", "privesc", "privilege",
                  "audit", "malware", "forensic", "bounty"]),
    ("architecture", ["architect", "architecture", "c4", "design", "domain",
                      "ddd", "adr", "diagram", "pattern", "microservice",
                      "event-driven", "system"]),
    ("data-ai", ["rag", "llm", "ml", "ai", "agent", "prompt", "langchain",
                 "langgraph", "embedding", "vector", "neural", "model",
                 "nlp", "gpt", "claude", "gemini"]),
    ("infrastructure", ["docker", "aws", "gcp", "azure", "k8s", "kubernetes",
                        "terraform", "ci", "cd", "deploy", "cloud",
                        "serverless", "vercel", "pipeline", "devops"]),
    ("testing", ["test", "tdd", "bdd", "qa", "spec", "playwright", "jest",
                 "pytest", "mock", "fixture", "coverage"]),
    ("workflow", ["workflow", "automation", "job", "trigger", "inngest",
                  "queue", "cron", "orchestrat"]),
    ("business", ["seo", "marketing", "copy", "pricing", "growth", "cro",
                  "ads", "brand", "sales", "crm"]),
    ("development", ["react", "typescript", "python", "javascript", "node",
                     "nextjs", "tailwind", "css", "html", "api", "rest",
                     "graphql", "debug", "refactor", "code", "dev",
                     "frontend", "backend", "fullstack"]),
    ("general", []),
]


def name_to_triggers(name: str) -> list:
    parts = name.replace("_", "-").split("-")
    triggers = [name]
    triggers += [" ".join(parts)]
    triggers += parts
    return list(dict.fromkeys(t for t in triggers if len(t) > 2))


def detect_category(name: str) -> str:
    name_lower = name.lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in name_lower for kw in keywords):
            return category
    return "general"


def extract_description(skill_dir: Path, name: str) -> str:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return name.replace("-", " ").title()

    text = skill_md.read_text(errors="ignore")

    fm = re.search(r'^description:\s*(.+)$', text, re.MULTILINE)
    if fm:
        return fm.group(1).strip()[:120]

    for line in text.splitlines():
        line = line.strip()
        if (line and not line.startswith("#") and
                not line.startswith("---") and
                not line.startswith("name:") and
                not line.startswith("description:") and
                len(line) > 15):
            return line[:120]

    return name.replace("-", " ").capitalize()


def build_manifest(skill_dir: Path) -> dict:
    name = skill_dir.name
    category = detect_category(name)
    desc = extract_description(skill_dir, name)
    triggers = name_to_triggers(name)

    dangerous_names = [
        "metasploit", "exploit", "privilege-escalation",
        "malware", "reverse-shell", "keylogger",
    ]
    dangerous = any(d in name.lower() for d in dangerous_names)

    return {
        "name": name,
        "category": category,
        "description": desc,
        "triggers": triggers,
        "tags": [category, *triggers[:3]],
        "entry": "SKILL.md",
        "timeout": 120 if dangerous else 60,
        "dangerous": dangerous,
        "requires": [],
    }


def main(force: bool = False):
    if not SKILLS_DIR.exists():
        print(f"ERROR: {SKILLS_DIR} not found.")
        sys.exit(1)

    dirs = [d for d in sorted(SKILLS_DIR.iterdir()) if d.is_dir()]
    created = 0
    skipped = 0

    for d in dirs:
        mf_path = d / "manifest.json"
        if mf_path.exists() and not force:
            skipped += 1
            continue

        manifest = build_manifest(d)
        mf_path.write_text(json.dumps(manifest, indent=2))
        created += 1

    print(f"\n✓ Done — {created} created, {skipped} skipped")
    print(f"  Total skills: {len(dirs)}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    main(force=force)

"""
JARVIS v2 — tools/skill_creator.py
Self-learning skill creator. 3 modes:
1. Extract from conversation
2. Learn from unmatched queries
3. On-demand generation
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.text import Text


def score_skill_md(content: str, name: str) -> dict:
    scores = {}
    words = len(content.split())
    if 80 <= words <= 600:
        scores["length"] = 20
    elif 40 <= words < 80 or 600 < words <= 1000:
        scores["length"] = 12
    else:
        scores["length"] = 5

    has_h1 = bool(re.search(r"^#\s+\S+", content, re.MULTILINE))
    scores["title"] = 18 if has_h1 else 8

    action_words = ["analyze", "check", "review", "create", "write",
                   "implement", "generate", "scan", "test", "build",
                   "design", "evaluate", "identify", "suggest", "return",
                   "provide", "follow", "always", "never", "output",
                   "format", "use", "apply", "consider"]
    hits = sum(1 for w in action_words if w in content.lower())
    scores["action"] = min(20, hits * 3)

    headers = len(re.findall(r"^#{1,3} ", content, re.MULTILINE))
    bullets = len(re.findall(r"^[\-\*] ", content, re.MULTILINE))
    numbered = len(re.findall(r"^\d+\. ", content, re.MULTILINE))
    scores["structure"] = min(20, (headers * 5) + (bullets + numbered) * 2)

    name_parts = [p.lower() for p in name.replace("-", " ").split()]
    hits = sum(1 for p in name_parts if p in content.lower() and len(p) > 3)
    scores["relevance"] = min(20, hits * 7)

    total = sum(scores.values())
    return {
        "scores": scores, "total": total,
        "grade": "A" if total >= 85 else "B" if total >= 70 else "C" if total >= 55 else "F",
        "pass": total >= 60,
    }


class SkillCreator:
    def __init__(self, brain, skills_dir, console, settings):
        self.brain = brain
        self.skills_dir = skills_dir
        self.console = console
        self.settings = settings

    async def handle(self, query: str, conversation_history: list = None) -> str:
        ql = query.lower().strip()

        if "save this" in ql or "extract skill" in ql:
            name = self._extract_name(query)
            return await self.extract_from_conversation(
                name or "extracted-skill", conversation_history or [])

        if "learn from unmatched" in ql or "auto learn" in ql:
            return await self.learn_from_unmatched()

        return await self.on_demand_create(query)

    def _extract_name(self, query: str) -> Optional[str]:
        m = re.search(r'(?:called|named?|as)\s+["\'"]?([a-z0-9\-]+)["\'"]?',
                      query, re.IGNORECASE)
        return m.group(1).lower() if m else None

    async def extract_from_conversation(self, name: str, history: list) -> str:
        self.console.print(Text(f"\n  🧠 Extracting skill '{name}'...\n", style="bold #a78bfa"))

        turns = []
        for msg in history[-20:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")[:600]
            turns.append(f"[{role.upper()}]: {content}")

        history_text = "\n\n".join(turns) if turns else "(no history)"

        prompt = f"""Analyze this conversation and extract a reusable skill guide.
CONVERSATION: {history_text}
Generate a SKILL.md for "{name}" with: Overview, Key Principles, Step-by-step Instructions, Common Pitfalls, Output Format.
200-400 words, imperative voice. Output ONLY the markdown."""

        skill_md = await self.brain.complete([{"role": "user", "content": prompt}])
        return await self._save_skill(name, skill_md, self._guess_category(skill_md + name),
                                     source="conversation_extract")

    async def learn_from_unmatched(self) -> str:
        log_path = self.settings.SKILL_INDEX_PATH.parent / "router.log"
        if not log_path.exists():
            return "No router.log found yet."

        unmatched = []
        for line in log_path.read_text().splitlines():
            try:
                entry = json.loads(line)
                if entry.get("score", 1.0) < 0.5:
                    unmatched.append(entry.get("query", ""))
            except Exception:
                pass

        if not unmatched:
            return "No unmatched queries — routing is working great!"

        unmatched = unmatched[-100:]
        self.console.print(Text(f"\n  🔍 Found {len(unmatched)} unmatched queries...\n",
                               style="bold #a78bfa"))

        prompt = f"""Analyze unmatched queries and propose 2-4 new skills.
Queries: {chr(10).join(f'  - {q}' for q in unmatched)}
Respond with JSON: {{"clusters": [{{"skill_name": "name", "category": "cat", "description": "desc", "triggers": ["t1","t2"]}}]}}"""

        resp = await self.brain.complete([{"role": "user", "content": prompt}])
        try:
            clean = re.sub(r'```(?:json)?\n?', '', resp).strip().rstrip('```').strip()
            data = json.loads(clean)
        except json.JSONDecodeError:
            return f"Could not parse response."

        results = []
        for cluster in data.get("clusters", []):
            sname = cluster.get("skill_name", "auto-skill")
            desc = cluster.get("description", "")
            cat = cluster.get("category", "general")
            triggers = cluster.get("triggers", [])
            skill_md = await self._generate_skill_md(sname, desc, triggers)
            result = await self._save_skill(sname, skill_md, cat, source="auto_learn",
                                           triggers=triggers)
            results.append(result)

        return "\n\n".join(results)

    async def on_demand_create(self, query: str) -> str:
        name, description = self._parse_skill_request(query)
        self.console.print(Text(f"\n  ✨ Creating skill: {name}\n", style="bold #a78bfa"))

        category = self._guess_category(description + " " + name)
        skill_md = await self._generate_skill_md(name, description, [])
        result = await self._save_skill(name, skill_md, category, source="on_demand")
        return result

    def _parse_skill_request(self, query: str) -> tuple:
        q = query.strip()

        m = re.search(r'new skill:\s*([a-z0-9\-]+)\s*[—\-]+\s*(.+)', q, re.IGNORECASE)
        if m:
            return m.group(1).lower(), m.group(2).strip()

        m = re.search(r'(?:create|make|new)\s+(?:a\s+)?skill\s+(?:for|to)\s+(.+)',
                      q, re.IGNORECASE)
        if m:
            desc = m.group(1).strip()
            return self._name_from_desc(desc), desc

        m = re.search(r'teach\s+(?:yourself|jarvis)\s+(?:to\s+)?(.+)', q, re.IGNORECASE)
        if m:
            desc = m.group(1).strip()
            return self._name_from_desc(desc), f"Agent skill to {desc}"

        desc = q.replace("create skill", "").replace("new skill", "").strip()
        return self._name_from_desc(desc), desc

    def _name_from_desc(self, desc: str) -> str:
        stop = {"a", "an", "the", "for", "to", "in", "of", "and", "or", "with", "that", "this"}
        words = [w.lower() for w in re.findall(r"[a-zA-Z]+", desc) if w.lower() not in stop][:4]
        return "-".join(words) or "custom-skill"

    async def _generate_skill_md(self, name: str, description: str, example_queries: list) -> str:
        examples_text = ""
        if example_queries:
            examples_text = "\n\nUser queries this skill handles:\n" + \
                           "\n".join(f"  - {q}" for q in example_queries[:5])

        prompt = f"""Write a SKILL.md for an AI agent named Jarvis.
Skill: {name} — {description}{examples_text}
Include: Overview, When to Use, Instructions (5-10 steps), Output Format, Key Principles.
300-500 words, imperative voice. Output ONLY the markdown."""

        return await self.brain.complete([{"role": "user", "content": prompt}])

    async def _save_skill(self, name: str, skill_md: str, category: str = "general",
                         source: str = "on_demand", triggers: list = None) -> str:
        name = re.sub(r"[^a-z0-9\-]", "-", name.lower()).strip("-")
        if not name:
            name = "auto-skill"

        quality = score_skill_md(skill_md, name)
        self.console.print(Text(
            f"\n  Quality: {quality['total']}/100 [{quality['grade']}]",
            style=f"bold {'#10b981' if quality['pass'] else '#ef4444'}"
        ))

        if not quality["pass"]:
            self.console.print(Text("  Improving...", style="dim #f59e0b"))
            skill_md = await self._improve_skill_md(skill_md, name, quality)
            quality = score_skill_md(skill_md, name)

        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(skill_md)

        if not triggers:
            triggers = self._extract_triggers(skill_md, name)

        manifest = {
            "name": name, "category": category,
            "description": self._extract_description(skill_md, name),
            "triggers": triggers, "tags": [category, source],
            "entry": "SKILL.md", "timeout": 60, "dangerous": False,
            "requires": [], "quality": quality["total"], "source": source,
        }
        (skill_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        self.console.print(Text(f"\n  ✓ Skill created: {name} ({quality['total']}/100)\n",
                               style="bold #10b981"))
        return f"Skill '{name}' created (quality: {quality['total']}/100)."

    async def _improve_skill_md(self, skill_md: str, name: str, quality: dict) -> str:
        issues = [f"- Low {dim} ({score}/20)" for dim, score in quality["scores"].items() if score < 14]
        prompt = f"""Rewrite this SKILL.md for '{name}' to fix:
{chr(10).join(issues)}
Current: {skill_md}
Make it more specific, structured, 200-500 words. Output ONLY the markdown."""
        return await self.brain.complete([{"role": "user", "content": prompt}])

    def _extract_triggers(self, skill_md: str, name: str) -> list:
        name_parts = [p for p in name.replace("-", " ").split() if len(p) > 2]
        stop = {"the", "a", "an", "is", "are", "to", "of", "in", "for", "and", "or",
               "with", "this", "that", "you", "your", "should", "will", "can", "use"}
        words = re.findall(r"\b[a-z]{4,}\b", skill_md.lower())
        freq = {}
        for w in words:
            if w not in stop:
                freq[w] = freq.get(w, 0) + 1
        top = sorted(freq, key=freq.get, reverse=True)[:8]
        return list(dict.fromkeys(name_parts + top))[:10] or [name]

    def _extract_description(self, skill_md: str, name: str) -> str:
        lines = skill_md.splitlines()
        found_h1 = False
        for line in lines:
            line = line.strip()
            if line.startswith("# "):
                found_h1 = True
                continue
            if found_h1 and line and not line.startswith("#"):
                return re.sub(r"[*_`]", "", line)[:120]
        return f"{name.replace('-', ' ').title()} — custom Jarvis skill"

    def _guess_category(self, text: str) -> str:
        text_l = text.lower()
        rules = [
            ("security", ["security", "hack", "vuln", "pentest", "exploit", "audit"]),
            ("data-ai", ["ai", "ml", "model", "embedding", "rag", "llm", "agent"]),
            ("infrastructure", ["docker", "kubernetes", "aws", "cloud", "deploy", "terraform"]),
            ("testing", ["test", "tdd", "jest", "pytest", "playwright", "qa"]),
            ("architecture", ["architect", "design", "system", "microservice", "api", "pattern"]),
            ("business", ["seo", "marketing", "growth", "copy", "sales"]),
            ("development", ["code", "python", "javascript", "react", "debug", "refactor"]),
        ]
        for cat, keywords in rules:
            if any(k in text_l for k in keywords):
                return cat
        return "general"


SKILL_CREATE_PATTERNS = (
    "create a skill", "create skill", "new skill:", "new skill ",
    "make a skill", "make skill", "teach yourself", "teach jarvis",
    "save this as a skill", "save this skill", "extract skill from",
    "learn from unmatched", "auto learn",
)


def is_skill_create(query: str) -> bool:
    ql = query.lower().strip()
    return any(p in ql for p in SKILL_CREATE_PATTERNS)

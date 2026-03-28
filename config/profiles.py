"""
JARVIS v2 — config/profiles.py

Startup profiles that configure Jarvis behavior.
Usage:
  python3 main.py --lite
  python3 main.py --full
  python3 main.py --safe
  python3 main.py --bugbounty
  python3 main.py --coding
"""


PROFILES = {
    "default": {
        "name": "Default",
        "mode": "act",
        "memory_profile": "default",
        "description": "Standard Jarvis — all features, action mode",
    },
    "lite": {
        "name": "Lite",
        "mode": "concise",
        "memory_profile": "default",
        "description": "Minimal output, fast responses, low RAM",
    },
    "full": {
        "name": "Full",
        "mode": "detailed",
        "memory_profile": "default",
        "description": "Detailed responses, full context",
    },
    "safe": {
        "name": "Safe",
        "mode": "act",
        "memory_profile": "default",
        "safe_mode": True,
        "description": "No dangerous commands, recon only, no exploits",
    },
    "bugbounty": {
        "name": "Bug Bounty",
        "mode": "act",
        "memory_profile": "bounty",
        "description": "Bug bounty hunting mode — recon, scan, report",
        "extra_persona": (
            "\nYou are in BUG BOUNTY mode."
            "\n- Focus on finding vulnerabilities"
            "\n- Use real security tools and techniques"
            "\n- Always check scope before scanning"
            "\n- Format findings as bug bounty reports"
            "\n- Prioritize by severity (Critical > High > Medium > Low)"
            "\n- Include reproduction steps"
            "\n- Suggest CVSS scores"
        ),
    },
    "coding": {
        "name": "Coding",
        "mode": "act",
        "memory_profile": "coding",
        "description": "Code-focused — write code, debug, review",
        "extra_persona": (
            "\nYou are in CODING mode."
            "\n- Write clean, production-ready code"
            "\n- Include error handling"
            "\n- Follow best practices for the language"
            "\n- Add brief comments for complex logic"
            "\n- Suggest tests"
        ),
    },
    "personal": {
        "name": "Personal",
        "mode": "detailed",
        "memory_profile": "personal",
        "description": "Personal assistant — notes, planning, ideas",
    },
    "automation": {
        "name": "Automation",
        "mode": "act",
        "memory_profile": "automation",
        "description": "Task automation — scripts, cron, batch jobs",
        "extra_persona": (
            "\nYou are in AUTOMATION mode."
            "\n- Write shell scripts and automation"
            "\n- Use cron, systemd timers, or at"
            "\n- Make everything repeatable"
            "\n- Log everything"
        ),
    },
}


def get_profile(name: str) -> dict:
    return PROFILES.get(name, PROFILES["default"])


def list_profiles() -> dict:
    return {k: v["description"] for k, v in PROFILES.items()}

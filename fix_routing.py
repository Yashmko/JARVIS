"""Fix router by adding better triggers to key security skills."""
import json
from pathlib import Path

fixes = {
    "sql-injection-testing": {
        "extra_triggers": ["sql injection", "what is sql injection", "sqli", "sql attack", "database injection", "sql vuln"]
    },
    "vulnerability-scanner": {
        "extra_triggers": ["xss vulnerabilities", "find xss", "find vulnerabilities", "find bugs", "scan for vulns", "nmap", "how does nmap work", "nmap tutorial"]
    },
    "systematic-debugging": {
        "extra_triggers": ["debug python", "debug my code", "fix my code", "code not working"]
    },
    "ethical-hacking-methodology": {
        "extra_triggers": ["buffer overflow", "explain buffer overflow", "what is buffer overflow", "overflow attack", "stack overflow attack"]
    },
    "linux-privilege-escalation": {
        "extra_triggers": ["privesc", "privilege escalation", "root access", "sudo exploit"]
    },
    "burp-suite-testing": {
        "extra_triggers": ["xss test", "csrf test", "web vulnerability", "web app security", "intercept traffic"]
    },
    "api-fuzzing-bug-bounty": {
        "extra_triggers": ["api security", "api vulnerability", "api testing", "rest api hack", "api fuzzing"]
    },
    "frontend-mobile-security-xss-scan": {
        "extra_triggers": ["xss", "cross site scripting", "script injection", "dom xss", "reflected xss"]
    },
}

skills_dir = Path("skills")
fixed = 0
not_found = []

for skill_name, data in fixes.items():
    mf = skills_dir / skill_name / "manifest.json"
    if not mf.exists():
        not_found.append(skill_name)
        continue
    manifest = json.loads(mf.read_text())
    existing = set(manifest.get("triggers", []))
    new_triggers = list(existing | set(data["extra_triggers"]))
    manifest["triggers"] = new_triggers
    mf.write_text(json.dumps(manifest, indent=2))
    fixed += 1
    print(f"  ✓ {skill_name} — added {len(data['extra_triggers'])} triggers")

if not_found:
    print(f"\n  Not found: {not_found}")

print(f"\n✓ Fixed {fixed} skills")

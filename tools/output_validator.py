"""
JARVIS v2 — tools/output_validator.py
Blocks hallucinated and fake exploit outputs.
"""
import re

HALLUCINATION_PATTERNS = [
    r"subdomain\d+\.target\.com",
    r"api\.example\.com",
    r"example\.com/api/",
    r"\[YOUR_TARGET\]",
    r"\[TARGET_DOMAIN\]",
    r"<target>",
    r"placeholder",
]

FAKE_PHRASES = [
    "example output",
    "sample output",
    "for example",
    "hypothetical",
    "simulated",
]

def is_fake_exploit(output: str) -> bool:
    patterns = [
        r"requests\.post\(",
        r"sqli_payload\s*=",
        r"csrf_payload\s*=",
        r"xss_payload\s*=",
        r"# SQL Injection",
        r"# CSRF",
        r"# XSS",
    ]
    for p in patterns:
        if re.search(p, output, re.IGNORECASE):
            return True
    
    if "example api" in lower or "hypothetical" in lower:
        return True
    if "developer portal" in lower and "curl" in lower:
        return True

    return False

def is_hallucinated(output: str) -> bool:
    lower = output.lower()

    for pattern in HALLUCINATION_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            return True

    for phrase in FAKE_PHRASES:
        if phrase in lower:
            return True

    if is_fake_exploit(output):
        return True

    
    if "example api" in lower or "hypothetical" in lower:
        return True
    if "developer portal" in lower and "curl" in lower:
        return True

    return False

def safe_llm_response(output: str) -> str:
    if not output or output.strip() == "":
        return "(no output)"

    if is_hallucinated(output):
        return (
            "⚠ Blocked fake AI output.\n"
            "Run real commands instead:\n"
            "  !subfinder -d target.com\n"
            "  !nmap -sV target.com\n"
            "  !curl -I https://target.com\n"
        )

    return output

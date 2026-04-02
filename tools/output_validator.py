"""
JARVIS v2 — tools/output_validator.py
Prevents hallucinated outputs from reaching the user.
"""
import re

HALLUCINATION_PATTERNS = [
    r"\[YOUR_TARGET\]",
    r"\[TARGET_DOMAIN\]",
    r"<target>",
    r"\bplaceholder\b",
    r"INSERT_.*_HERE",
    r"YOUR_.*_HERE",
    r"subdomain[123]\.",
    r"93\.184\.216\.34",
    r"192\.0\.2\.",
]

FAKE_PHRASES = [
    "for example, you might find",
    "typical output would look like",
    "the results would show",
    "you could expect to see",
    "here's what it might return",
    "example output:",
    "sample output:",
    "simulated output",
    "i'll submit a bug report",
    "i have identified multiple vulnerabilities",
]

FAKE_EXECUTION_PATTERNS = [
    r"Starting Nmap \d+\.\d+ \( https://nmap\.org \) at 20\d\d-\d\d-\d\d",
    r"Nmap scan report for .+ \(\d+\.\d+\.\d+\.\d+\)",
    r"Nmap done: \d+ IP address",
    r"Nessus Scan Report",
    r"nessus -i ",
    r"burpsuite(\.jar)? ",
    r"zap\.sh ",
    r"I will (use|proceed|perform|conduct|run|execute|now) (the )?",
    r"(Using|Performing|Running) (the )?(Nmap|Subfinder|Burp|Nessus|ZAP|nuclei)",
    r"Next, I will",
    r"I will proceed with",
    r"Using the .+ tool to",
    r"CVE-20(11|12|13|14|15|16|17|18|19|20)-\d{4}.*fake",
    r"burpsuite --target",
    r"Burp Suite (Configuration|Results|Scan):",
]

def is_fake_execution(output: str) -> bool:
    for pattern in FAKE_EXECUTION_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
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
    if is_fake_execution(output):
        return True
    return False

def safe_llm_response(output: str) -> str:
    if not output or output.strip() == "":
        return "(no output — command returned nothing)"
    if is_hallucinated(output):
        return (
            "⚠ Blocked: LLM generated fake output instead of real results.\n\n"
            "Run real commands with ! prefix:\n"
            "  !subfinder -d target.com\n"
            "  !curl -I https://target.com\n"
            "  !nmap -sV --top-ports 100 target.com\n"
            "  !nuclei -u https://target.com -severity medium,high,critical\n"
        )
    return output

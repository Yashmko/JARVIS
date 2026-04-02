"""
JARVIS v2 — autonomous safe mode patches.
Adds: domain allowlist, no localhost drift, real execution only.
"""
import re

# Commands that are ALWAYS blocked in autonomous mode
AUTONOMOUS_BLOCKED = [
    "rm ", "dd ", "mkfs", "shutdown", "reboot",
    "> /dev/", "format ", "fdisk", "parted",
    "chmod 777", "chown root",
]

# Commands allowed in autonomous recon mode
RECON_SAFE_COMMANDS = [
    "curl", "wget", "dig", "nslookup", "whois",
    "nmap", "subfinder", "httpx", "nuclei", "ffuf",
    "amass", "assetfinder", "waybackurls", "gau",
    "grep", "cat", "head", "tail", "wc", "sort",
    "python3", "jq", "cut", "awk", "sed",
]

def validate_autonomous_command(cmd: str, target: str = None) -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    Enforces: no blocked commands, no localhost drift if target set.
    """
    cmd_lower = cmd.lower().strip()

    # Hard blocks
    for blocked in AUTONOMOUS_BLOCKED:
        if blocked in cmd_lower:
            return False, f"Blocked dangerous command: {blocked}"

    # Localhost drift prevention
    if target:
        localhost_patterns = [r'\blocalhost\b', r'127\.0\.0\.1', r'0\.0\.0\.0']
        for pat in localhost_patterns:
            if re.search(pat, cmd, re.IGNORECASE):
                return False, (
                    f"Blocked: command targets localhost but active target is {target}. "
                    f"Use the actual target domain."
                )

    # Must start with a known safe command in autonomous mode
    first_word = cmd_lower.split()[0] if cmd_lower.split() else ""
    if first_word not in RECON_SAFE_COMMANDS:
        return False, f"Command '{first_word}' not in autonomous safe list"

    return True, "ok"

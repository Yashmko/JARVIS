"""
JARVIS v2 — tools/safe_json.py
Safe JSON parsing — handles escape errors from /api paths.
"""
import json
import re

def safe_parse_json(text: str) -> dict:
    if not text:
        return {}
    text = re.sub(r'```(?:json)?\n?', '', text).strip().rstrip('`').strip()

    def fix_escapes(s: str) -> str:
        valid = {'"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u'}
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                next_char = s[i + 1]
                if next_char in valid:
                    result.append(s[i])
                    result.append(next_char)
                    i += 2
                else:
                    result.append(next_char)
                    i += 2
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return json.loads(fix_escapes(text))
        except json.JSONDecodeError:
            result = {}
            for match in re.finditer(r'"(\w+)"\s*:\s*"([^"]*)"', text):
                result[match.group(1)] = match.group(2)
            return result

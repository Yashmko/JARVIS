"""
tools/kimi_swarm.py — Kimi K2.5 full-power integration for JARVIS
Modes: Instant | Thinking | Agent | Swarm (100 parallel sub-agents)
"""
import asyncio
import json
import os
import requests
from typing import Generator

NVIDIA_BASE = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "moonshotai/kimi-k2.5"

# Tools JARVIS exposes to Kimi for agentic use
JARVIS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run a shell command on the local system. Use for recon, file ops, nmap, subfinder, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file and return its contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    }
]


def _execute_tool(name: str, args: dict) -> str:
    """Execute a tool call from Kimi and return result."""
    import subprocess
    if name == "shell":
        cmd = args.get("command", "")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            out = result.stdout.strip() or result.stderr.strip()
            return out[:3000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out after 30s"
        except Exception as e:
            return f"Error: {e}"
    elif name == "write_file":
        try:
            path = args["path"]
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            with open(path, "w") as f:
                f.write(args["content"])
            return f"✓ Written to {path}"
        except Exception as e:
            return f"Error: {e}"
    elif name == "read_file":
        try:
            with open(args["path"]) as f:
                return f.read()[:3000]
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown tool: {name}"


class KimiK25:
    """Kimi K2.5 client with all 4 modes + tool use for JARVIS."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _call(self, messages, thinking=False, tools=None, stream=False, max_tokens=4096):
        payload = {
            "model": MODEL,
            "messages": messages,
            "temperature": 1.0 if thinking else 0.6,
            "max_tokens": max_tokens,
            "stream": stream,
            "chat_template_kwargs": {"thinking": thinking},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return requests.post(NVIDIA_BASE, headers=self.headers, json=payload)

    def instant(self, prompt: str, system: str = "You are JARVIS, an autonomous AI agent.") -> str:
        """Fast response, no reasoning traces."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        r = self._call(messages, thinking=False)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def think(self, prompt: str, system: str = "You are JARVIS, an autonomous AI agent.") -> tuple[str, str]:
        """Deep thinking mode. Returns (answer, reasoning_trace)."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        r = self._call(messages, thinking=True, max_tokens=8192)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        answer = msg.get("content", "")
        reasoning = msg.get("reasoning_content", "")
        return answer, reasoning

    def agent(self, prompt: str, system: str = "You are JARVIS. Use tools to complete tasks autonomously.", max_steps: int = 10) -> str:
        """
        Agent mode: Kimi autonomously calls tools (shell, file ops) to complete tasks.
        Loops until done or max_steps reached.
        """
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        step = 0
        print(f"[Kimi Agent] Starting task: {prompt[:60]}...")

        while step < max_steps:
            step += 1
            r = self._call(messages, thinking=False, tools=JARVIS_TOOLS)
            r.raise_for_status()
            choice = r.json()["choices"][0]
            msg = choice["message"]
            finish = choice.get("finish_reason", "")

            messages.append(msg)

            # Check for tool calls
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                print(f"[Kimi Agent] Step {step}: calling {len(tool_calls)} tool(s)")
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    print(f"  → {fn_name}({list(fn_args.values())[0] if fn_args else ''})")
                    result = _execute_tool(fn_name, fn_args)
                    print(f"  ← {result[:100]}{'...' if len(result)>100 else ''}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result
                    })
                continue

            # No tool calls = final answer
            final = msg.get("content", "")
            print(f"[Kimi Agent] Done in {step} steps")
            return final

        return "Max steps reached. Partial result in conversation history."

    def swarm(self, prompt: str, system: str = "You are JARVIS orchestrating a swarm of agents.") -> str:
        """
        Swarm mode: Kimi self-directs up to 100 parallel sub-agents.
        Uses thinking mode + tools. Best for complex research/bounty tasks.
        """
        swarm_system = system + """

You are running in SWARM MODE. For complex tasks:
1. Decompose into parallel subtasks
2. Spawn specialized sub-agents for each subtask
3. Each sub-agent should use tools independently
4. Synthesize results from all agents into a final report

Use shell tool for: recon, scanning, data gathering
Use write_file to save intermediate results
Think step by step, run tasks in parallel where possible.
"""
        messages = [{"role": "system", "content": swarm_system}, {"role": "user", "content": prompt}]
        step = 0
        max_steps = 30  # Swarm can do up to 100 steps, we cap at 30 for safety
        print(f"[Kimi Swarm] Initializing swarm for: {prompt[:60]}...")

        while step < max_steps:
            step += 1
            r = self._call(messages, thinking=True, tools=JARVIS_TOOLS, max_tokens=8192)
            r.raise_for_status()
            choice = r.json()["choices"][0]
            msg = choice["message"]

            messages.append(msg)

            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                print(f"[Kimi Swarm] Step {step}: {len(tool_calls)} parallel tool calls")
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    print(f"  ⚡ {fn_name}: {str(list(fn_args.values())[0])[:80]}")
                    result = _execute_tool(fn_name, fn_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result
                    })
                continue

            final = msg.get("content", "")
            reasoning = msg.get("reasoning_content", "")
            if reasoning:
                print(f"[Kimi Swarm] Reasoning trace: {reasoning[:200]}...")
            print(f"[Kimi Swarm] Completed in {step} steps")
            return final

        return "Swarm max steps reached."


def get_kimi(settings) -> KimiK25:
    """Get a KimiK25 instance from JARVIS settings."""
    key = getattr(settings, "NVIDIA_API_KEY", "") or os.getenv("NVIDIA_API_KEY", "")
    if not key:
        raise ValueError("NVIDIA_API_KEY not set")
    return KimiK25(key)

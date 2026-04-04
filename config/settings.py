"""
JARVIS v2 — config/settings.py
Single source of truth. 7 free LLM providers.
All use OpenAI-compatible API — one package handles everything.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


class Settings:
    # ── API Keys ──────────────────────────────────
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    TOGETHER_API_KEY: str = os.getenv("TOGETHER_API_KEY", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    HF_API_KEY: str = os.getenv("HF_API_KEY", "")

    # ── Model fallback chain ─────────────────────
    # Format: (name, base_url, key_attr, model)
    # All use OpenAI-compatible endpoints — one library handles all 7
    # Order: fastest free tier first → slowest last
    MODEL_CHAIN = [
        (
            "kimi-k2.5",
            "https://integrate.api.nvidia.com/v1",
            "NVIDIA_API_KEY",
            "moonshotai/kimi-k2.5",
        ),
        (
            "kimi-k2",
            "https://integrate.api.nvidia.com/v1",
            "NVIDIA_API_KEY",
            "moonshotai/kimi-k2",
        ),
        (
            "groq",
            "https://api.groq.com/openai/v1",
            "GROQ_API_KEY",
            "llama-3.3-70b-versatile",
        ),
        (
            "cerebras",
            "https://api.cerebras.ai/v1",
            "CEREBRAS_API_KEY",
            "llama-3.3-70b",
        ),
        (
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            "GEMINI_API_KEY",
            "gemini-2.0-flash",
        ),
        (
            "together",
            "https://api.together.xyz/v1",
            "TOGETHER_API_KEY",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        ),
        (
            "mistral",
            "https://api.mistral.ai/v1",
            "MISTRAL_API_KEY",
            "mistral-small-latest",
        ),
        (
            "openrouter",
            "https://openrouter.ai/api/v1",
            "OPENROUTER_API_KEY",
            "meta-llama/llama-3.3-70b-instruct:free",
        ),
        (
            "huggingface",
            "https://api-inference.huggingface.co/v1/",
            "HF_API_KEY",
            "meta-llama/Llama-3.1-8B-Instruct",
        ),
    ]

    # ── Fast model for classify() — cheapest/fastest ──
    FAST_MODEL = (
        "kimi-k2",
        "https://integrate.api.nvidia.com/v1",
        "NVIDIA_API_KEY",
        "moonshotai/kimi-k2",
    )
    FAST_MODEL_BACKUP = (
        "groq",
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
        "llama-3.1-8b-instant",
    )

    # ── Memory ────────────────────────────────────
    MEMORY_WINDOW: int = 20
    MEMORY_DB: Path = BASE_DIR / "memory" / "history.db"
    SKILL_INDEX_PATH: Path = BASE_DIR / "memory" / "skill_index.npy"

    # ── Skills ────────────────────────────────────
    SKILLS_DIR: Path = BASE_DIR / "skills"
    ROUTER_THRESHOLD: float = 0.12

    # ── Executor ──────────────────────────────────
    DEFAULT_TIMEOUT: int = 60
    DANGEROUS_TIMEOUT: int = 120
    MAX_RETRIES: int = 1

    # ── Persona ───────────────────────────────────
    PERSONA_FILE: Path = BASE_DIR / "config" / "persona.md"
    ALIASES_FILE: Path = BASE_DIR / "config" / "aliases.json"

    @property
    def PERSONA(self) -> str:
        if self.PERSONA_FILE.exists():
            return self.PERSONA_FILE.read_text()
        return "You are Jarvis, an autonomous AI agent with 1,300 skills."

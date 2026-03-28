"""
JARVIS v2 — brain.py

Multi-provider LLM layer — 7 free providers, one unified API.
Every provider uses OpenAI-compatible endpoints, so one library
handles all of them. No separate methods per provider.

Fallback chain:
  Groq → Cerebras → Gemini → Together → Mistral → OpenRouter → HuggingFace

classify() uses Groq 8B (fastest) for routing decisions.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from openai import AsyncOpenAI

log = logging.getLogger(__name__)


class BrainClient:
    """Unified LLM interface across 7 free providers."""

    def __init__(self, settings):
        self.settings = settings
        self._clients: dict[str, AsyncOpenAI] = {}
        self._usage_log = settings.MEMORY_DB.parent / "usage.log"
        self._usage_log.parent.mkdir(parents=True, exist_ok=True)

    def _client(self, name: str, base_url: str, api_key: str) -> AsyncOpenAI:
        """Get or create a cached client. One per provider."""
        if name not in self._clients:
            self._clients[name] = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
        return self._clients[name]

    # ═════════════════════════════════════════════
    # PUBLIC API
    # ═════════════════════════════════════════════

    async def stream(self, messages: list) -> AsyncGenerator[str, None]:
        """
        Stream a response. Tries each provider in MODEL_CHAIN order.
        Skips providers without API keys.
        Yields string tokens as they arrive.
        """
        last_err = None

        for name, base_url, key_attr, model in self.settings.MODEL_CHAIN:
            api_key = getattr(self.settings, key_attr, "")
            if not api_key:
                continue

            try:
                client = self._client(name, base_url, api_key)
                token_count = 0

                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                )

                async for chunk in response:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        token_count += 1
                        yield content

                self._log_usage(name, model, token_count)
                return

            except Exception as e:
                log.warning(f"[brain] {name}/{model} failed: {e}")
                last_err = e
                continue

        raise RuntimeError(f"All 7 LLM providers failed. Last error: {last_err}")

    async def complete(self, messages: list) -> str:
        """Non-streaming complete. Returns full response string."""
        parts = []
        async for chunk in self.stream(messages):
            parts.append(chunk)
        return "".join(parts)

    async def classify(self, query: str) -> dict:
        """
        Fast pre-classification using cheapest model (Groq 8B).
        Returns: {intent, complexity, category_hint, needs_workflow}
        Used by router to narrow skill search.
        """
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a query classifier. Respond ONLY with valid JSON.\n"
                    "Fields: intent (str), complexity (low/med/high), "
                    "category_hint (one of: architecture/security/data-ai/"
                    "development/infrastructure/testing/workflow/business/general), "
                    "needs_workflow (bool)"
                ),
            },
            {"role": "user", "content": f"Classify: {query}"},
        ]

        name, base_url, key_attr, model = self.settings.FAST_MODEL
        api_key = getattr(self.settings, key_attr, "")

        if not api_key:
            return self._default_classification(query)

        try:
            client = self._client(name + "_fast", base_url, api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=prompt,
                max_tokens=150,
            )
            text = response.choices[0].message.content or ""
            # Strip markdown fences if model wraps JSON in ```
            clean = text.strip().strip("`").strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()
            return json.loads(clean)
        except Exception as e:
            log.debug(f"[brain] classify failed: {e}")
            return self._default_classification(query)

    # ═════════════════════════════════════════════
    # INTERNAL
    # ═════════════════════════════════════════════

    @staticmethod
    def _default_classification(query: str) -> dict:
        return {
            "intent": query,
            "complexity": "med",
            "category_hint": "general",
            "needs_workflow": False,
        }

    def _log_usage(self, provider: str, model: str, tokens: int):
        entry = {
            "ts": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "tokens": tokens,
        }
        try:
            with open(self._usage_log, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

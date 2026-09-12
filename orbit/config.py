"""
orbit.config
============

Central config **and the single place a model is constructed**.

Every layer reasons through `make_llm()`. Nothing else in the codebase may
build an LLM client or name a model id — that is what lets the team switch
provider with an `.env` edit and zero code changes.

    ORBIT_LLM_PROVIDER=openrouter   -> OpenRouter gateway, PREFIXED model id
    ORBIT_LLM_PROVIDER=anthropic    -> Anthropic direct, bare model id

Model ids differ by provider and it is the easiest way to break a run:
OpenRouter wants `anthropic/claude-sonnet-4.6` (prefixed, dotted), Anthropic
direct wants `claude-sonnet-4-6` (bare, dashed). This module is the only file
that has to know that.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv is optional at import time
    pass


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True)
class Settings:
    # Which provider make_llm() builds from: "openrouter" | "anthropic".
    llm_provider: str = os.getenv("ORBIT_LLM_PROVIDER", "anthropic").strip().lower()
    # The one shared Claude account key (see .env.example).
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    # OpenRouter: one gateway to many models, and the rate-limit fallback.
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    # Optional Browser Use Cloud key (reaches Claude too via provider prefix).
    browser_use_api_key: str = os.getenv("BROWSER_USE_API_KEY", "")
    # Optional Exa key — a SUPPORTING research tool, never the demo path.
    exa_api_key: str = os.getenv("EXA_API_KEY", "")
    # Model the agent reasons with. Must match the provider's id convention.
    model: str = os.getenv("ORBIT_MODEL", "claude-sonnet-4-6")
    # A short tag so a shared-key run is traceable to a developer in logs.
    developer_tag: str = os.getenv("ORBIT_DEV_TAG", "unknown-dev")
    # Portal the demo drives.
    portal_url: str = os.getenv("ORBIT_PORTAL_URL", "http://127.0.0.1:5000")
    headless: bool = os.getenv("ORBIT_HEADLESS", "false").lower() == "true"

    @property
    def llm_key(self) -> str:
        """The key for the *selected* provider, or "" if it isn't configured."""
        if self.llm_provider == "openrouter":
            return self.openrouter_api_key
        return self.anthropic_api_key


settings = Settings()


def has_llm() -> bool:
    """True when the selected provider has a key.

    The agent uses this to fall back to its offline planner instead of crashing,
    so a fresh clone with no `.env` still runs.
    """
    return bool(settings.llm_key)


def require_key() -> str:
    if not has_llm() and not settings.browser_use_api_key:
        raise RuntimeError(
            f"No LLM key for provider {settings.llm_provider!r}. Copy .env.example "
            "to .env and set OPENROUTER_API_KEY (or ANTHROPIC_API_KEY). See your "
            "DEV_*.md, 'The LLM provider'."
        )
    return settings.llm_key or settings.browser_use_api_key


# --------------------------------------------------------------------------- #
# The one model factory.
# --------------------------------------------------------------------------- #
class ChatModel:
    """A minimal async chat client that speaks both providers' wire formats.

    Deliberately not tied to browser-use's Chat* classes: those move between
    versions, and Dev 1 has not pinned a version yet. One `ainvoke` is all the
    agent needs, so this stays a thin, stable seam.
    """

    def __init__(self, provider: str, model: str, api_key: str) -> None:
        self.provider = provider
        self.model = model
        self._api_key = api_key

    def __repr__(self) -> str:  # never leak the key into a log line
        return f"ChatModel(provider={self.provider!r}, model={self.model!r})"

    async def ainvoke(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        """Send chat messages, return the assistant's text.

        `messages` uses the OpenAI shape ({"role": ..., "content": ...}); the
        Anthropic branch reshapes it, because Anthropic takes `system` as a
        top-level field rather than a message.
        """
        import httpx

        if self.provider == "openrouter":
            url, headers = OPENROUTER_URL, {"Authorization": f"Bearer {self._api_key}"}
            payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        else:
            system = " ".join(m["content"] for m in messages if m["role"] == "system")
            url = ANTHROPIC_URL
            headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"}
            payload = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [m for m in messages if m["role"] != "system"],
            }
            if system:
                payload["system"] = system

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"{self.provider} returned {response.status_code} for model "
                    f"{self.model!r}: {response.text[:300]}"
                )
            data = response.json()

        if self.provider == "openrouter":
            return data["choices"][0]["message"]["content"]
        return "".join(block.get("text", "") for block in data.get("content", []))


def make_llm(model: str | None = None) -> ChatModel:
    """Build the model for the configured provider. The ONLY way to get one.

    Raises if the selected provider has no key — call `has_llm()` first if you
    want to degrade gracefully instead.
    """
    key = require_key()
    provider = settings.llm_provider if settings.llm_provider in {"openrouter", "anthropic"} else "anthropic"
    return ChatModel(provider=provider, model=model or settings.model, api_key=key)

"""
orbit.config
============

Central config + the SHARED Claude account key.

All three developers share ONE Anthropic account, so there is a single
ANTHROPIC_API_KEY in the .env file. See the "Shared Claude account" section in
your DEV_*.md before you run anything — a shared key means shared rate limits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv is optional at import time
    pass


@dataclass(frozen=True)
class Settings:
    # The one shared Claude account key (see .env.example).
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    # Optional Browser Use Cloud key (reaches Claude too via provider prefix).
    browser_use_api_key: str = os.getenv("BROWSER_USE_API_KEY", "")
    # Model the agent reasons with. Anthropic through the shared account.
    model: str = os.getenv("ORBIT_MODEL", "claude-sonnet-4-6")
    # A short tag so a shared-key run is traceable to a developer in logs.
    developer_tag: str = os.getenv("ORBIT_DEV_TAG", "unknown-dev")
    # Portal the demo drives.
    portal_url: str = os.getenv("ORBIT_PORTAL_URL", "http://127.0.0.1:5000")
    headless: bool = os.getenv("ORBIT_HEADLESS", "false").lower() == "true"


settings = Settings()


def require_key() -> str:
    if not settings.anthropic_api_key and not settings.browser_use_api_key:
        raise RuntimeError(
            "No LLM key found. Copy .env.example to .env and add the shared "
            "ANTHROPIC_API_KEY (see your DEV_*.md, 'Shared Claude account')."
        )
    return settings.anthropic_api_key or settings.browser_use_api_key

"""
orbit.main   ---  the integration point. Kept small on purpose.
==============================================================

Wires the three layers together behind the shared contracts. Swap a mock for a
real implementation as each developer finishes theirs — nothing else changes.

    python -m orbit.main "Process today's 5 orders"

By default it runs fully offline (mock browser + console human/activity) so a
brand-new clone runs with zero setup. Pass --real to use the Browser Use
controller once Dev 1's implementation is ready.
"""

from __future__ import annotations

import argparse
import asyncio

from orbit.agent import OrbitAgent
from orbit.browser import BrowserUseController, MockBrowserController
from orbit.config import settings
from orbit.control import ConsoleActivitySink, ConsoleGateway


def _try_web_ui():
    """Attempt to import Dev 3's web UI components.

    Returns (WebGateway, WebActivitySink) if available, None otherwise.
    Allows the agent to run with the web UI when Dev 3's code is merged,
    falling back to console defaults when it isn't.
    """
    try:
        from orbit.ui.activity import WebActivitySink, WebGateway
        return WebGateway, WebActivitySink
    except ImportError:
        return None


async def _run(goal: str, real: bool, web_ui: bool) -> None:
    browser = BrowserUseController(headless=settings.headless) if real else MockBrowserController()

    # Pick gateway and activity sink: web UI if requested and available,
    # otherwise console defaults.
    web_components = _try_web_ui() if web_ui else None
    if web_components:
        WebGateway, WebActivitySink = web_components
        gateway = WebGateway()
        activity = WebActivitySink()
    else:
        if web_ui:
            print("[WARN] --web-ui requested but orbit.ui.activity not found. "
                  "Falling back to console.")
        gateway = ConsoleGateway()
        activity = ConsoleActivitySink()

    agent = OrbitAgent(
        browser=browser,
        gateway=gateway,
        activity=activity,
    )
    outcome = await agent.run(goal)
    print(f"\n=== outcome: {outcome} ===")


def main() -> None:
    p = argparse.ArgumentParser(description="Orbit browser employee")
    p.add_argument("goal", nargs="?", default="Process today's 5 orders")
    p.add_argument("--real", action="store_true",
                   help="use the real Browser Use controller (Dev 1)")
    p.add_argument("--web-ui", action="store_true",
                   help="use Dev 3's web gateway/activity sink if available")
    args = p.parse_args()
    asyncio.run(_run(args.goal, args.real, args.web_ui))


if __name__ == "__main__":
    main()

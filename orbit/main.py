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


async def _run(goal: str, real: bool) -> None:
    browser = BrowserUseController(headless=settings.headless) if real else MockBrowserController()
    agent = OrbitAgent(
        browser=browser,
        gateway=ConsoleGateway(),      # Dev 3 swaps in ui.activity.WebGateway
        activity=ConsoleActivitySink(),  # Dev 3 swaps in ui.activity.WebActivitySink
    )
    outcome = await agent.run(goal)
    print(f"\n=== outcome: {outcome} ===")


def main() -> None:
    p = argparse.ArgumentParser(description="Orbit browser employee")
    p.add_argument("goal", nargs="?", default="Process today's 5 orders")
    p.add_argument("--real", action="store_true", help="use the real Browser Use controller")
    args = p.parse_args()
    asyncio.run(_run(args.goal, args.real))


if __name__ == "__main__":
    main()

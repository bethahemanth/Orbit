"""Smoke test: the wired loop runs offline with mocks. Keep this green."""

import asyncio

from orbit.agent import OrbitAgent
from orbit.browser import MockBrowserController
from orbit.control import ConsoleActivitySink, ConsoleGateway


def test_loop_runs_offline():
    agent = OrbitAgent(MockBrowserController(), ConsoleGateway(), ConsoleActivitySink())
    outcome = asyncio.run(agent.run("Process today's 5 orders"))
    assert outcome in {"done", "max_steps_reached"}


def test_contracts_importable():
    from orbit import contracts
    assert contracts.ActionType.CLICK.value == "click"

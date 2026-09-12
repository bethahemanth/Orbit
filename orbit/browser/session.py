"""
orbit.browser.session   ---  DEV 1 (Browser) owns this file.
============================================================

Responsibility (spec Section 8, Member 1): a reliable browser session and
execution layer built on the Browser Use runtime + Chrome/Playwright. It turns
an `AgentAction` into a real browser action and reports what it sees.

You implement `BrowserUseController`. A `MockBrowserController` is provided so
Dev 2 and Dev 3 can run the loop before your real one is ready — keep it in sync
with the contract, but do not build features into the mock.

Reference: browser-use README / docs.browser-use.com
    from browser_use import Agent, Browser, ChatAnthropic, Tools
"""

from __future__ import annotations

from orbit.contracts import (
    ActionResult,
    ActionType,
    AgentAction,
    BrowserController,
    Observation,
)


class BrowserUseController(BrowserController):
    """Real controller backed by Browser Use.

    TODO(dev1):
      * In start(): create a `Browser` (local Chrome; reuse a real profile for
        authenticated sessions — see browser-use real_browser.py example).
      * In observe(): return the live DOM/accessibility summary + screenshot.
      * In execute(): map each ActionType onto a browser-use capability
        (navigate/click/type/select/scroll/back). Prefer semantic targeting
        (role/text) over CSS selectors — that is the whole thesis.
      * Keep this layer stateless about the *task*. It executes; it never asks
        the user and never decides the next step.
    """

    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self._browser = None  # browser_use.Browser instance

    async def start(self) -> None:
        # from browser_use import Browser
        # self._browser = Browser(headless=self.headless)
        # await self._browser.start()
        raise NotImplementedError("dev1: create and start the Browser Use browser")

    async def stop(self) -> None:
        # if self._browser:
        #     await self._browser.stop()
        raise NotImplementedError("dev1: stop the browser cleanly")

    async def observe(self) -> Observation:
        raise NotImplementedError("dev1: return current page state as Observation")

    async def execute(self, action: AgentAction) -> ActionResult:
        raise NotImplementedError("dev1: perform the action via Browser Use")


class MockBrowserController(BrowserController):
    """Deterministic fake so Dev 2/Dev 3 can run without a real browser.

    Records the actions it was told to do and returns canned observations.
    """

    def __init__(self) -> None:
        self.history: list[AgentAction] = []
        self._url = "about:blank"

    async def start(self) -> None:
        self._url = "http://127.0.0.1:5000"

    async def stop(self) -> None:
        pass

    async def observe(self) -> Observation:
        return Observation(
            url=self._url,
            title="Mock Portal",
            page_summary="Mock page. Orders table with 5 rows; a 'Process' button per row.",
            interactive_elements=["'Process' button", "'Search' field", "'Submit order' button"],
        )

    async def execute(self, action: AgentAction) -> ActionResult:
        self.history.append(action)
        if action.type == ActionType.NAVIGATE and action.target:
            self._url = action.target
        return ActionResult(
            success=True,
            message=f"[mock] executed {action.type.value} on {action.target!r}",
            observation=await self.observe(),
        )

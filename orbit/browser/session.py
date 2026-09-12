"""
orbit.browser.session   ---  DEV 1 (Browser) owns this file.
============================================================

Responsibility (spec Section 8, Member 1): a reliable browser session and
execution layer built on the Browser Use runtime + Chrome/Playwright. It turns
an `AgentAction` into a real browser action and reports what it sees.

You implement `BrowserUseController`. A `MockBrowserController` is provided so
Dev 2 and Dev 3 can run the loop before your real one is ready — keep it in sync
with the contract, but do not build features into the mock.

Installed browser-use version: 0.13.x. Its low-level API is quite different
from older releases — there is no `browser_use.Browser(headless=...)` with a
plain `.start()`/`.get_current_page()`. Confirmed live against this repo's
`orbit/portal/app.py` (see docs/DEV_1_BROWSER.md step 2/3):

    from browser_use import BrowserSession, Tools

    browser = BrowserSession(headless=True)
    await browser.start()
    tools = Tools()
    await tools.navigate(url="http://127.0.0.1:5000", browser_session=browser)
    state = await browser.get_browser_state_summary(include_screenshot=False)
    state.dom_state.selector_map        # dict[int, EnhancedDOMTreeNode] — the
                                         # live interactive elements, already
                                         # indexed by role/accessible-name, not
                                         # by CSS selector.
    await tools.click(index=<idx>, browser_session=browser)

`Tools` (aliased `Controller`) exposes one async method per registered browser
capability (`navigate`, `click`, `input`, `select_dropdown`, `scroll`,
`go_back`, ...) that all take `browser_session=` plus the action's own
parameters — see `browser_use/tools/service.py`.

Reference: docs.browser-use.com
"""

from __future__ import annotations

import asyncio
import difflib
import re
from typing import TYPE_CHECKING

from orbit.contracts import (
    ActionResult,
    ActionType,
    AgentAction,
    BrowserController,
    Observation,
)

if TYPE_CHECKING:
    from browser_use.dom.views import EnhancedDOMTreeNode

# Small settle delay after an action that may trigger a page load (click/type
# submit, select). browser-use's own navigate/click handlers already wait on
# network-idle internally, but a short extra beat protects against JS-driven
# UI updates that don't fire a CDP "load" event.
_ACTION_SETTLE_S = 0.3

# A target like "the 'Process' button" or "Search field" describes an element
# semantically. These are stripped before matching so only the meaningful
# words remain — never a CSS selector, per the project thesis.
_ROLE_WORDS = {
    "button", "buttons", "field", "fields", "input", "inputs", "box",
    "link", "links", "dropdown", "select", "checkbox", "option", "menu",
    "tab", "row", "element",
}
_STOP_WORDS = {"the", "a", "an", "on", "in", "for", "of", "click", "select"}

# Only these roles/tags are ever resolved as click/type/select targets. Rows,
# cells, and other structural containers stay out of the running — otherwise
# a target like "the 'Process' button" can substring-match a row whose status
# cell says "processed" before it ever reaches the actual button.
_ACTIONABLE_ROLES = {
    "button", "link", "textbox", "searchbox", "combobox", "listbox",
    "checkbox", "radio", "menuitem", "menuitemcheckbox", "menuitemradio",
    "tab", "switch", "slider", "spinbutton", "option",
    "a", "input", "select", "textarea",
}

# Below this score, resolving a semantic target raises instead of guessing.
_MATCH_THRESHOLD = 0.5


class ElementNotFoundError(Exception):
    """No live element matched a semantic target description."""


class BrowserUseController(BrowserController):
    """Real controller backed by Browser Use.

    Keeps this layer dumb on purpose: it executes actions and reports what it
    sees. It does not decide what to do next (that's the agent) and does not
    talk to the user.
    """

    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self._browser = None  # browser_use.BrowserSession instance
        self._tools = None  # browser_use.Tools instance

    async def start(self) -> None:
        from browser_use import BrowserSession, Tools

        self._browser = BrowserSession(headless=self.headless)
        await self._browser.start()
        self._tools = Tools()

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.stop()
        self._browser = None
        self._tools = None

    async def observe(self) -> Observation:
        browser = self._require_browser()
        state = await browser.get_browser_state_summary(include_screenshot=False)
        return Observation(
            url=state.url,
            title=state.title,
            page_summary=state.dom_state.llm_representation(),
            interactive_elements=_describe_elements(state.dom_state.selector_map),
            raw={"selector_map_size": len(state.dom_state.selector_map)},
        )

    async def execute(self, action: AgentAction) -> ActionResult:
        browser = self._require_browser()
        tools = self._tools
        try:
            t = action.type
            bu_result = None  # browser-use's own ActionResult — can carry a
            # soft `.error` on failure without raising, so it must be checked
            # explicitly rather than treated as success just because nothing
            # threw.
            if t == ActionType.NAVIGATE:
                if not action.target:
                    return ActionResult(success=False, message="navigate needs a target URL")
                bu_result = await tools.navigate(url=action.target, browser_session=browser)
            elif t == ActionType.CLICK:
                idx = await self._resolve_index(action.target)
                bu_result = await tools.click(index=idx, browser_session=browser)
            elif t == ActionType.TYPE:
                idx = await self._resolve_index(action.target)
                bu_result = await tools.input(index=idx, text=action.value or "", browser_session=browser)
            elif t == ActionType.SELECT:
                idx = await self._resolve_index(action.target)
                bu_result = await tools.select_dropdown(index=idx, text=action.value or "", browser_session=browser)
            elif t == ActionType.SCROLL:
                down = (action.value or "down").strip().lower() != "up"
                bu_result = await tools.scroll(down=down, browser_session=browser)
            elif t == ActionType.BACK:
                bu_result = await tools.go_back(browser_session=browser)
            else:
                return ActionResult(success=False, message=f"unhandled action type {t!r}")

            if bu_result is not None and getattr(bu_result, "error", None):
                return ActionResult(
                    success=False,
                    message=f"{t.value} on {action.target!r} failed",
                    observation=await self.observe(),
                    error=str(bu_result.error),
                )

            await asyncio.sleep(_ACTION_SETTLE_S)
            return ActionResult(
                success=True,
                message=f"did {t.value} on {action.target!r}",
                observation=await self.observe(),
            )
        except ElementNotFoundError as e:
            return ActionResult(success=False, message="target not found on page", error=str(e))
        except Exception as e:  # browser-use surfaces CDP/browser errors as plain Exceptions
            return ActionResult(success=False, message="action failed", error=str(e))

    # ------------------------------------------------------------------ #
    # Semantic targeting — resolve a text description to a live element
    # index. Never a fixed CSS selector; the index comes fresh from the
    # current accessibility/DOM state, so it survives renamed labels and
    # re-rendered pages. Cascade: exact accessible-name match, then
    # substring, then fuzzy — first tier that clears the bar wins.
    # ------------------------------------------------------------------ #
    async def _resolve_index(self, target: str | None) -> int:
        if not target:
            raise ElementNotFoundError("no target description given")
        browser = self._require_browser()
        state = await browser.get_browser_state_summary(include_screenshot=False)
        selector_map = state.dom_state.selector_map
        if not selector_map:
            raise ElementNotFoundError("page has no interactive elements right now")

        # Only ever resolve against clickable/editable roles — a row or cell
        # can share words with the real target (e.g. a "processed" status
        # cell vs. a "Process order" button) and must never win.
        candidates = {idx: node for idx, node in selector_map.items() if _is_actionable(node)}
        if not candidates:
            raise ElementNotFoundError("page has no clickable/editable elements right now")

        cleaned = _clean_target(target)
        best_idx, best_score = None, 0.0
        for idx, node in candidates.items():
            score = _match_score(cleaned, node)
            if score > best_score:
                best_idx, best_score = idx, score

        if best_idx is None or best_score < _MATCH_THRESHOLD:
            candidates_desc = ", ".join(_describe_elements(selector_map)[:8])
            raise ElementNotFoundError(
                f"no element matches {target!r} (best score {best_score:.2f}). "
                f"Visible elements: {candidates_desc}"
            )
        return best_idx

    def _require_browser(self):
        if self._browser is None or self._tools is None:
            raise RuntimeError("browser not started; call start() first")
        return self._browser


class MockBrowserController(BrowserController):
    """Deterministic fake so Dev 2/Dev 3 can run without a real browser.

    Records the actions it was told to do and returns canned observations.
    """

    def __init__(self) -> None:
        self.history: list[AgentAction] = []
        self._url = "about:blank"
        self._orders_left = 5

    async def start(self) -> None:
        self._url = "http://127.0.0.1:5000"

    async def stop(self) -> None:
        pass

    async def observe(self) -> Observation:
        if self._orders_left > 0:
            summary = f"Mock page. Orders table with {self._orders_left} rows; a 'Process' button per row."
            elements = ["'Process' button", "'Search' field", "'Submit order' button"]
        else:
            summary = "Mock page. All orders processed."
            elements = ["'Search' field"]
        return Observation(
            url=self._url,
            title="Mock Portal",
            page_summary=summary,
            interactive_elements=elements,
        )

    async def execute(self, action: AgentAction) -> ActionResult:
        self.history.append(action)
        if action.type == ActionType.NAVIGATE and action.target:
            self._url = action.target
        elif action.type == ActionType.CLICK:
            if self._orders_left > 0:
                self._orders_left -= 1
        return ActionResult(
            success=True,
            message=f"[mock] executed {action.type.value} on {action.target!r}",
            observation=await self.observe(),
        )


# ---------------------------------------------------------------------- #
# Helpers — pure functions so they're easy to unit test without a browser.
# ---------------------------------------------------------------------- #
def _element_name(node: "EnhancedDOMTreeNode") -> str:
    if node.ax_node and node.ax_node.name:
        return node.ax_node.name
    return node.get_meaningful_text_for_llm() or ""


def _element_role(node: "EnhancedDOMTreeNode") -> str:
    if node.ax_node and node.ax_node.role:
        return node.ax_node.role
    return node.tag_name or "element"


def _is_actionable(node: "EnhancedDOMTreeNode") -> bool:
    return _element_role(node).lower() in _ACTIONABLE_ROLES


def _describe_elements(selector_map: dict) -> list[str]:
    described = []
    for idx, node in selector_map.items():
        if not _is_actionable(node):
            continue
        role = _element_role(node)
        name = _element_name(node).strip()
        described.append(f"[{idx}] {role}: '{name}'" if name else f"[{idx}] {role}")
    return described


def _clean_target(target: str) -> str:
    """Strip descriptor scaffolding ("the ... button") down to the meaning."""
    quoted = re.search(r"['\"]([^'\"]+)['\"]", target)
    if quoted:
        return quoted.group(1).strip().lower()
    words = re.findall(r"[\w']+", target.lower())
    words = [w for w in words if w not in _ROLE_WORDS and w not in _STOP_WORDS]
    return " ".join(words) or target.strip().lower()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _match_score(cleaned: str, node: "EnhancedDOMTreeNode") -> float:
    """Whole-word match first, so "process" never brushes past "processed".

    A plain substring check would let a target like "process" match inside
    an unrelated word ("processed") just because the characters line up —
    that's exactly how a status cell can outrank the real button. Comparing
    tokenized words keeps the match meaning-based, not character-based.
    """
    name = _element_name(node).strip()
    name_l = name.lower()
    if not cleaned or not name_l:
        return 0.0
    if cleaned == name_l:
        return 1.0

    cleaned_tokens = _tokenize(cleaned)
    name_tokens = _tokenize(name)
    if cleaned_tokens and name_tokens:
        if all(t in name_tokens for t in cleaned_tokens):
            return min(0.7 + 0.15 * (len(cleaned_tokens) / len(name_tokens)), 0.95)
        if all(t in cleaned_tokens for t in name_tokens):
            return 0.8

    return difflib.SequenceMatcher(None, cleaned, name_l).ratio()

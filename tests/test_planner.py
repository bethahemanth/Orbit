"""Tests for orbit.agent.planner — parse_json, classify_risk, planners."""

import asyncio
import pytest

from orbit.agent.planner import (
    LLMPlanner,
    RulePlanner,
    classify_risk,
    parse_json,
)
from orbit.contracts import ActionType, AgentAction, Observation, RiskLevel


# ------------------------------------------------------------------ #
# parse_json
# ------------------------------------------------------------------ #
class TestParseJson:
    def test_bare_json(self):
        raw = '{"type": "click", "target": "button", "reason": "test", "risk": "safe"}'
        result = parse_json(raw)
        assert result["type"] == "click"
        assert result["target"] == "button"

    def test_json_in_code_fences(self):
        raw = '```json\n{"type": "navigate", "target": "http://x.com"}\n```'
        result = parse_json(raw)
        assert result["type"] == "navigate"

    def test_json_with_prose_prefix(self):
        raw = 'Here\'s the action: {"type": "click", "target": "Submit"}'
        result = parse_json(raw)
        assert result["type"] == "click"

    def test_json_with_trailing_explanation(self):
        raw = '{"type": "finish", "reason": "done"}\nThat completes the task.'
        result = parse_json(raw)
        assert result["type"] == "finish"

    def test_nested_braces_in_strings(self):
        raw = '{"type": "click", "target": "button {with} braces"}'
        result = parse_json(raw)
        assert result["target"] == "button {with} braces"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="empty reply"):
            parse_json("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty reply"):
            parse_json("   \n  ")

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="no JSON object found"):
            parse_json("Just some plain text with no JSON at all.")


# ------------------------------------------------------------------ #
# classify_risk
# ------------------------------------------------------------------ #
class TestClassifyRisk:
    def test_submit_is_consequential(self):
        assert classify_risk("submit") == RiskLevel.CONSEQUENTIAL

    def test_submit_order_is_consequential(self):
        assert classify_risk("Submit Order") == RiskLevel.CONSEQUENTIAL

    def test_delete_is_consequential(self):
        assert classify_risk("delete this item") == RiskLevel.CONSEQUENTIAL

    def test_navigate_is_safe(self):
        assert classify_risk("navigate") == RiskLevel.SAFE

    def test_process_is_safe(self):
        # "process" is NOT in CONSEQUENTIAL_WORDS
        assert classify_risk("process") == RiskLevel.SAFE

    def test_none_is_safe(self):
        assert classify_risk(None) == RiskLevel.SAFE

    def test_empty_string_is_safe(self):
        assert classify_risk("") == RiskLevel.SAFE


# ------------------------------------------------------------------ #
# RulePlanner
# ------------------------------------------------------------------ #
class TestRulePlanner:
    def test_navigates_when_not_on_portal(self):
        planner = RulePlanner("http://127.0.0.1:5000")
        obs = Observation(url="about:blank")
        action = asyncio.run(planner.next_action("Process orders", obs))
        assert action.type == ActionType.NAVIGATE
        assert "127.0.0.1:5000" in (action.target or "")

    def test_clicks_process_button(self):
        planner = RulePlanner("http://127.0.0.1:5000")
        obs = Observation(
            url="http://127.0.0.1:5000/orders",
            interactive_elements=["'Process' button", "'Search' field"],
        )
        action = asyncio.run(planner.next_action("Process orders", obs))
        assert action.type == ActionType.CLICK
        assert "Process" in (action.target or "")

    def test_finishes_when_no_actionable_element(self):
        planner = RulePlanner("http://127.0.0.1:5000")
        obs = Observation(
            url="http://127.0.0.1:5000/orders",
            interactive_elements=["'Search' field", "'Help' link"],
        )
        action = asyncio.run(planner.next_action("Process orders", obs))
        assert action.type == ActionType.FINISH

    def test_finishes_after_max_repeats(self):
        planner = RulePlanner("http://127.0.0.1:5000", max_repeats=2)
        obs = Observation(
            url="http://127.0.0.1:5000/orders",
            interactive_elements=["'Process' button"],
        )
        # Click 3 times — third should trigger finish
        asyncio.run(planner.next_action("go", obs))
        asyncio.run(planner.next_action("go", obs))
        action = asyncio.run(planner.next_action("go", obs))
        assert action.type == ActionType.FINISH


# ------------------------------------------------------------------ #
# LLMPlanner._to_action
# ------------------------------------------------------------------ #
class TestLLMPlannerToAction:
    def test_valid_click(self):
        data = {"type": "click", "target": "Process button", "reason": "advance", "risk": "safe"}
        action = LLMPlanner._to_action(data)
        assert action.type == ActionType.CLICK
        assert action.target == "Process button"

    def test_ask_user_with_value(self):
        data = {"type": "ask_user", "value": "Which John?", "reason": "ambiguous"}
        action = LLMPlanner._to_action(data)
        assert action.type == ActionType.ASK_USER
        assert action.value == "Which John?"

    def test_ask_user_without_value_uses_reason(self):
        data = {"type": "ask_user", "reason": "need clarification"}
        action = LLMPlanner._to_action(data)
        assert action.type == ActionType.ASK_USER
        assert action.value == "need clarification"

    def test_ask_user_without_value_or_reason_uses_default(self):
        data = {"type": "ask_user"}
        action = LLMPlanner._to_action(data)
        assert action.value == "Could you clarify what you'd like me to do?"

    def test_risk_backstop_submit_button(self):
        # Model says safe, but target says "submit" — backstop overrides
        data = {"type": "click", "target": "Submit Order", "risk": "safe"}
        action = LLMPlanner._to_action(data)
        assert action.risk == RiskLevel.CONSEQUENTIAL

    def test_model_marks_consequential(self):
        data = {"type": "click", "target": "Process", "risk": "consequential"}
        action = LLMPlanner._to_action(data)
        assert action.risk == RiskLevel.CONSEQUENTIAL

    def test_invalid_action_type_raises(self):
        data = {"type": "fly_to_moon"}
        with pytest.raises(ValueError, match="unusable action type"):
            LLMPlanner._to_action(data)

    def test_missing_type_raises(self):
        data = {"target": "button"}
        with pytest.raises(ValueError, match="unusable action type"):
            LLMPlanner._to_action(data)

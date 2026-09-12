"""
tests/test_portal.py   ---  DEV 3 product layer tests.
======================================================

Portal routes, WebActivitySink, WebGateway, and RunManager tests.
All offline — no Chrome, API key, or network needed.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time

import pytest

from orbit.portal.app import GATEWAY, RUN_MANAGER, SINK, app
from orbit.portal.orders import ORDERS
from orbit.ui.activity import WebActivitySink, WebGateway


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client():
    """Flask test client with fresh order state."""
    app.config["TESTING"] = True
    # Reset orders to pending
    for o in ORDERS:
        o["status"] = "pending"
    # Reset run manager
    with RUN_MANAGER.lock:
        RUN_MANAGER.status = "idle"
        RUN_MANAGER.run_id = None
        RUN_MANAGER.goal = None
        RUN_MANAGER.outcome = None
        RUN_MANAGER.error = None
    with app.test_client() as c:
        yield c
    # Restore orders
    for o in ORDERS:
        o["status"] = "pending"


@pytest.fixture
def fresh_sink():
    """A fresh WebActivitySink for unit tests."""
    return WebActivitySink(max_history=10)


@pytest.fixture
def fresh_gateway():
    """A fresh WebGateway for unit tests."""
    return WebGateway()


# =========================================================================== #
# A. Portal route tests                                                       #
# =========================================================================== #
class TestPortalRoutes:
    def test_index_returns_200(self, client):
        rv = client.get("/")
        assert rv.status_code == 200

    def test_index_contains_all_customers(self, client):
        rv = client.get("/")
        html = rv.data.decode()
        for o in ORDERS:
            assert o["customer"] in html

    def test_search_filters_johns(self, client):
        rv = client.get("/?q=john")
        html = rv.data.decode()
        assert "John Smith" in html
        assert "John Carter" in html
        assert "John Diaz" in html
        assert "Aisha Khan" not in html
        assert "Marco Rossi" not in html

    def test_process_redirects_to_confirm(self, client):
        rv = client.post("/process/1", follow_redirects=False)
        assert rv.status_code == 302
        assert "/confirm/1" in rv.headers["Location"]

    def test_process_does_not_mutate(self, client):
        client.post("/process/1")
        order = next(o for o in ORDERS if o["id"] == 1)
        assert order["status"] == "pending"

    def test_confirm_get_shows_details(self, client):
        rv = client.get("/confirm/1")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "John Smith" in html
        assert "Widget A" in html
        assert "Confirm" in html

    def test_confirm_post_sets_processed(self, client):
        rv = client.post("/confirm/1", follow_redirects=False)
        assert rv.status_code == 302
        order = next(o for o in ORDERS if o["id"] == 1)
        assert order["status"] == "processed"

    def test_process_already_processed_returns_409(self, client):
        client.post("/confirm/1")  # Process first
        rv = client.post("/process/1")
        assert rv.status_code == 409

    def test_confirm_already_processed_returns_409(self, client):
        client.post("/confirm/1")
        rv = client.post("/confirm/1")
        assert rv.status_code == 409

    def test_unknown_order_returns_404(self, client):
        rv = client.post("/process/999")
        assert rv.status_code == 404

    def test_confirm_unknown_order_returns_404(self, client):
        rv = client.get("/confirm/999")
        assert rv.status_code == 404

    def test_only_target_order_processed(self, client):
        client.post("/confirm/1")
        for o in ORDERS:
            if o["id"] == 1:
                assert o["status"] == "processed"
            else:
                assert o["status"] == "pending"


# =========================================================================== #
# B. WebActivitySink tests                                                    #
# =========================================================================== #
class TestWebActivitySink:
    def test_emit_stores_in_history(self, fresh_sink):
        fresh_sink.emit("goal", {"goal": "test"})
        assert len(fresh_sink.recent()) == 1
        assert fresh_sink.recent()[0]["kind"] == "goal"
        assert fresh_sink.recent()[0]["goal"] == "test"

    def test_bounded_history(self, fresh_sink):
        for i in range(20):
            fresh_sink.emit("step", {"n": i})
        assert len(fresh_sink.recent()) == 10  # max_history=10

    def test_subscriber_receives_events(self, fresh_sink):
        q = fresh_sink.subscribe()
        fresh_sink.emit("observe", {"url": "http://x"})
        event = q.get(timeout=1)
        assert event["kind"] == "observe"
        assert event["url"] == "http://x"
        fresh_sink.unsubscribe(q)

    def test_multiple_subscribers(self, fresh_sink):
        q1 = fresh_sink.subscribe()
        q2 = fresh_sink.subscribe()
        fresh_sink.emit("act", {"success": True})
        e1 = q1.get(timeout=1)
        e2 = q2.get(timeout=1)
        assert e1["kind"] == "act"
        assert e2["kind"] == "act"
        fresh_sink.unsubscribe(q1)
        fresh_sink.unsubscribe(q2)

    def test_unsubscribe_safe(self, fresh_sink):
        q = fresh_sink.subscribe()
        fresh_sink.unsubscribe(q)
        fresh_sink.unsubscribe(q)  # Double unsubscribe should not raise
        fresh_sink.emit("test", {})
        assert q.empty()

    def test_unknown_kinds_stored(self, fresh_sink):
        fresh_sink.emit("future_event", {"data": 42})
        assert fresh_sink.recent()[-1]["kind"] == "future_event"


# =========================================================================== #
# C. WebGateway tests                                                         #
# =========================================================================== #
class TestWebGateway:
    def test_ask_and_resolve(self, fresh_gateway):
        from orbit.contracts import ClarificationRequest

        req = ClarificationRequest(
            question="Which John?",
            options=["John Smith", "John Carter", "John Diaz"],
        )

        result = [None]

        async def run_ask():
            result[0] = await fresh_gateway.ask(req)

        t = threading.Thread(target=lambda: asyncio.run(run_ask()))
        t.start()

        # Wait for pending to appear
        time.sleep(0.2)
        pending = fresh_gateway.get_pending()
        assert pending is not None
        assert pending["kind"] == "clarification"
        assert pending["question"] == "Which John?"
        assert "John Smith" in pending["options"]

        # Resolve
        ok = fresh_gateway.resolve(pending["id"], "John Smith")
        assert ok is True
        t.join(timeout=3)
        assert result[0] == "John Smith"

    def test_approve_and_resolve(self, fresh_gateway):
        from orbit.contracts import ApprovalRequest, AgentAction, ActionType, RiskLevel

        action = AgentAction(
            type=ActionType.CLICK,
            target="Submit button",
            risk=RiskLevel.CONSEQUENTIAL,
        )
        req = ApprovalRequest(action=action, summary="Click submit")

        result = [None]

        async def run_approve():
            result[0] = await fresh_gateway.approve(req)

        t = threading.Thread(target=lambda: asyncio.run(run_approve()))
        t.start()

        time.sleep(0.2)
        pending = fresh_gateway.get_pending()
        assert pending is not None
        assert pending["kind"] == "approval"
        assert pending["summary"] == "Click submit"

        ok = fresh_gateway.resolve(pending["id"], True)
        assert ok is True
        t.join(timeout=3)
        assert result[0] is True

    def test_reject_stale_id(self, fresh_gateway):
        ok = fresh_gateway.resolve("nonexistent-id", "answer")
        assert ok is False

    def test_no_pending_returns_none(self, fresh_gateway):
        assert fresh_gateway.get_pending() is None


# =========================================================================== #
# D. Gateway HTTP routes tests                                                #
# =========================================================================== #
class TestGatewayRoutes:
    def test_pending_empty(self, client):
        rv = client.get("/gateway/pending")
        data = rv.get_json()
        assert data["pending"] is None

    def test_answer_no_json(self, client):
        rv = client.post("/gateway/answer", data="not json")
        assert rv.status_code == 400

    def test_answer_missing_id(self, client):
        rv = client.post(
            "/gateway/answer",
            data=json.dumps({"answer": "x"}),
            content_type="application/json",
        )
        assert rv.status_code == 400

    def test_answer_stale_id(self, client):
        rv = client.post(
            "/gateway/answer",
            data=json.dumps({"id": "fake", "answer": "x"}),
            content_type="application/json",
        )
        assert rv.status_code == 409


# =========================================================================== #
# E. Run manager tests                                                        #
# =========================================================================== #
class TestRunManager:
    def test_status_idle(self, client):
        rv = client.get("/run/status")
        data = rv.get_json()
        assert data["status"] == "idle"

    def test_start_run_returns_202(self, client):
        rv = client.post(
            "/run",
            data=json.dumps({"goal": "Process orders"}),
            content_type="application/json",
        )
        assert rv.status_code == 202
        data = rv.get_json()
        assert data["status"] == "running"
        assert "run_id" in data

        # Wait for mock run to finish
        time.sleep(1)

    def test_empty_goal_returns_400(self, client):
        rv = client.post(
            "/run",
            data=json.dumps({"goal": ""}),
            content_type="application/json",
        )
        assert rv.status_code == 400

    def test_run_reaches_terminal_state(self, client):
        client.post(
            "/run",
            data=json.dumps({"goal": "Process orders"}),
            content_type="application/json",
        )
        # Wait for the mock run to finish (stub agent finishes immediately)
        time.sleep(2)
        rv = client.get("/run/status")
        data = rv.get_json()
        assert data["status"] in ("finished", "failed")


# =========================================================================== #
# F. Activity recent endpoint                                                 #
# =========================================================================== #
class TestActivityRecent:
    def test_recent_returns_list(self, client):
        rv = client.get("/activity/recent")
        assert rv.status_code == 200
        data = rv.get_json()
        assert isinstance(data, list)

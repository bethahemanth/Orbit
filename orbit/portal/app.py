"""
orbit.portal.app   ---  DEV 3 (Product/Demo) owns this file.
===========================================================

A tiny business portal the agent operates during the demo (spec Section 3, 8).
Deliberately generic: an orders table with a semantic "Process" control, a
search box, a two-step confirm flow, and the live activity/gateway UI.

Run it:
    python -m orbit.portal.app     # serves http://127.0.0.1:5000
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from typing import Any

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, url_for

from orbit.portal.orders import ORDERS
from orbit.ui.activity import WebActivitySink, WebGateway

app = Flask(__name__)

# Flip this in the demo to prove semantic recovery (spec Section 10, step 3).
RENAME_BUTTON = False

# Layout variation: when True, search moves below the table (semantic recovery).
SWAP_LAYOUT = False


# --------------------------------------------------------------------------- #
# Shared instances — created once per Flask process                           #
# --------------------------------------------------------------------------- #
SINK = WebActivitySink()
GATEWAY = WebGateway()


# --------------------------------------------------------------------------- #
# Run manager state                                                           #
# --------------------------------------------------------------------------- #
class RunManager:
    """Manages a single in-process agent run."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.status: str = "idle"  # idle | running | finished | failed
        self.run_id: str | None = None
        self.goal: str | None = None
        self.outcome: str | None = None
        self.error: str | None = None

    def start(self, goal: str, real: bool = False) -> str:
        """Start an agent run in a background thread. Returns run_id."""
        with self.lock:
            if self.status == "running":
                raise RuntimeError("A run is already active")
            self.run_id = str(uuid.uuid4())
            self.goal = goal
            self.status = "running"
            self.outcome = None
            self.error = None
            run_id = self.run_id

        thread = threading.Thread(
            target=self._run_thread,
            args=(goal, real, run_id),
            daemon=True,
        )
        thread.start()
        return run_id

    def _run_thread(self, goal: str, real: bool, run_id: str) -> None:
        """Target for the background daemon thread."""
        try:
            # Lazy imports to keep portal importable before real browser is done
            from orbit.agent import OrbitAgent
            from orbit.browser import MockBrowserController

            if real:
                from orbit.browser import BrowserUseController
                from orbit.config import settings
                browser = BrowserUseController(headless=settings.headless)
            else:
                browser = MockBrowserController()

            agent = OrbitAgent(
                browser=browser,
                gateway=GATEWAY,
                activity=SINK,
            )
            outcome = asyncio.run(agent.run(goal))

            with self.lock:
                if self.run_id == run_id:
                    self.status = "finished"
                    self.outcome = outcome
        except Exception as exc:
            with self.lock:
                if self.run_id == run_id:
                    self.status = "failed"
                    self.error = str(exc)

    def get_status(self) -> dict[str, Any]:
        """Return a JSON-safe status snapshot."""
        with self.lock:
            return {
                "status": self.status,
                "run_id": self.run_id,
                "goal": self.goal,
                "outcome": self.outcome,
                "error": self.error,
            }


RUN_MANAGER = RunManager()


# --------------------------------------------------------------------------- #
# Helper                                                                      #
# --------------------------------------------------------------------------- #
def _find_order(order_id: int) -> dict[str, Any] | None:
    for o in ORDERS:
        if o["id"] == order_id:
            return o
    return None


# --------------------------------------------------------------------------- #
# Portal routes — orders workflow                                             #
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    rows = [o for o in ORDERS if q in o["customer"].lower()] if q else ORDERS
    label = "Fulfil" if RENAME_BUTTON else "Process"
    return render_template(
        "index.html",
        orders=rows,
        label=label,
        q=request.args.get("q", ""),
        swap_layout=SWAP_LAYOUT,
    )


@app.route("/process/<int:order_id>", methods=["POST"])
def process(order_id: int):
    order = _find_order(order_id)
    if order is None:
        abort(404)
    if order["status"] == "processed":
        abort(409)
    # Do NOT mutate — redirect to confirmation page
    return redirect(url_for("confirm", order_id=order_id))


@app.route("/confirm/<int:order_id>")
def confirm(order_id: int):
    order = _find_order(order_id)
    if order is None:
        abort(404)
    label = "Fulfil" if RENAME_BUTTON else "Process"
    return render_template("confirm.html", order=order, label=label)


@app.route("/confirm/<int:order_id>", methods=["POST"])
def confirm_submit(order_id: int):
    order = _find_order(order_id)
    if order is None:
        abort(404)
    if order["status"] == "processed":
        abort(409)
    order["status"] = "processed"
    return redirect(url_for("index"))


# --------------------------------------------------------------------------- #
# Activity SSE stream                                                         #
# --------------------------------------------------------------------------- #
@app.route("/activity/stream")
def activity_stream():
    def generate():
        q = SINK.subscribe()
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except Exception:
                    # Keep-alive comment during idle periods
                    yield ": keep-alive\n\n"
        finally:
            SINK.unsubscribe(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/activity/recent")
def activity_recent():
    return jsonify(SINK.recent())


# --------------------------------------------------------------------------- #
# Gateway routes                                                              #
# --------------------------------------------------------------------------- #
@app.route("/gateway/pending")
def gateway_pending():
    pending = GATEWAY.get_pending()
    return jsonify({"pending": pending})


@app.route("/gateway/answer", methods=["POST"])
def gateway_answer():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    interaction_id = data.get("id")
    if not interaction_id:
        return jsonify({"error": "Missing interaction id"}), 400

    # Check what kind of answer we got
    if "answer" in data:
        answer = data["answer"]
    elif "approved" in data:
        val = data["approved"]
        if not isinstance(val, bool):
            return jsonify({"error": "approved must be a boolean"}), 400
        answer = val
    else:
        return jsonify({"error": "Must provide 'answer' or 'approved'"}), 400

    resolved = GATEWAY.resolve(interaction_id, answer)
    if not resolved:
        return jsonify({"error": "Unknown or stale interaction id"}), 409

    return jsonify({"status": "accepted"}), 202


# --------------------------------------------------------------------------- #
# Run manager routes                                                          #
# --------------------------------------------------------------------------- #
@app.route("/run", methods=["POST"])
def start_run():
    data = request.get_json(silent=True) or {}
    goal = data.get("goal", "").strip()
    if not goal:
        return jsonify({"error": "Non-empty goal required"}), 400

    real = data.get("real", False)

    try:
        run_id = RUN_MANAGER.start(goal, real=bool(real))
    except RuntimeError:
        return jsonify({"error": "A run is already active"}), 409

    return jsonify({"run_id": run_id, "status": "running"}), 202


@app.route("/run/status")
def run_status():
    return jsonify(RUN_MANAGER.get_status())


# --------------------------------------------------------------------------- #
# Entrypoint                                                                  #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

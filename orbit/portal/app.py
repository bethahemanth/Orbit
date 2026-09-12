"""
orbit.portal.app   ---  DEV 3 (Product/Demo) owns this file.
===========================================================

A tiny business portal the agent operates during the demo (spec Section 3, 8).
Deliberately generic: an orders table with a semantic "Process" control, a
search box, and a confirm step. DEV 3: add the UI-variation toggle (rename/move
the button) and the activity log panel here.

Run it:
    python -m orbit.portal.app     # serves http://127.0.0.1:5000
"""

from __future__ import annotations

from flask import Flask, redirect, render_template, request, url_for

from orbit.portal.orders import ORDERS

app = Flask(__name__)

# Flip this in the demo to prove semantic recovery (spec Section 10, step 3).
RENAME_BUTTON = False


@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    rows = [o for o in ORDERS if q in o["customer"].lower()] if q else ORDERS
    label = "Fulfil" if RENAME_BUTTON else "Process"
    return render_template("index.html", orders=rows, label=label, q=q)


@app.route("/process/<int:order_id>", methods=["POST"])
def process(order_id: int):
    for o in ORDERS:
        if o["id"] == order_id:
            o["status"] = "processed"
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

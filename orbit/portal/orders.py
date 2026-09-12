"""Sample order data for the demo business portal. DEV 3 owns this."""

from __future__ import annotations

# Note the three "John"s on purpose — that's the ambiguity demo (spec 3 & 10).
ORDERS = [
    {"id": 1, "customer": "John Smith",   "item": "Widget A", "qty": 2, "status": "pending"},
    {"id": 2, "customer": "John Carter",  "item": "Widget B", "qty": 1, "status": "pending"},
    {"id": 3, "customer": "John Diaz",    "item": "Widget C", "qty": 5, "status": "pending"},
    {"id": 4, "customer": "Aisha Khan",   "item": "Widget A", "qty": 3, "status": "pending"},
    {"id": 5, "customer": "Marco Rossi",  "item": "Widget D", "qty": 1, "status": "pending"},
]

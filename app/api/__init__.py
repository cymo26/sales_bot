"""FastAPI HTTP layer for SALES_BOT.

This package exposes the exact same operations that `db/queries.py` already
performs for the Streamlit UI, as REST endpoints for the React frontend.
No new business logic is introduced here — `service.py` is a Streamlit-free
port of `db/queries.py`'s SQL and algorithms (dedupe, domain normalization,
industry-conflict dry run, batched writes, etc.), and the routers are thin
request/response translation on top of it.
"""

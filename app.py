# =============================================================================
# app.py – COMPATIBILITY ENTRY POINT
# -----------------------------------------------------------------------------
# Only re-exports the FastAPI object built in wp_app/main.py so the old command
# still works:   python -m uvicorn app:app --reload --port 8001
#
# Rule: never put business logic here. Everything lives in the wp_app package.
# =============================================================================

"""Compatibility entry point for ``uvicorn app:app``."""

from wp_app.main import app


__all__ = ["app"]

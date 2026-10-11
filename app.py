"""Compatibility entry point for ``uvicorn app:app``."""

from wp_app.main import app


__all__ = ["app"]

"""Vercel entrypoint for the existing recorded-only server; no live workbench imports."""

from backend.src.workbench.release import app

__all__ = ["app"]

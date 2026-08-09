"""Vercel Serverless Function Entrypoint.

Exposes the ASGI FastAPI application instance for Vercel deployment.
"""

from src.api.main import app

__all__ = ["app"]

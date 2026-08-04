"""API layer: exposes the prediction pipeline over HTTP via FastAPI.

This layer is intentionally thin — route handlers only translate HTTP
requests into calls against the service classes in
``src.api.services``, which contain the actual business logic and are
fully testable without an HTTP server.
"""

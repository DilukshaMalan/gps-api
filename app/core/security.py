"""Optional API-key check. The key is shared between your own backend and this service."""
import hmac

from flask import Flask, current_app, request

from app.core.errors import ApiError


def register_api_key_check(app: Flask) -> None:
    @app.before_request
    def require_api_key() -> None:
        key = current_app.config["SETTINGS"].api_key
        if not key:                                   # no key configured -> open (local development)
            return
        if request.path.rstrip("/") == "/api/v1/health":
            return
        supplied = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(supplied.encode(), key.encode()):
            raise ApiError(401, "unauthorized", "Missing or invalid API key.")

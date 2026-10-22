"""One error shape for the whole API:  {"error": {"code": "...", "message": "..."}}"""
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class NotFoundError(ApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(404, code, message)


def _payload(code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}})


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return _payload(err.code, err.message), err.status

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        code = (err.name or "error").lower().replace(" ", "_")
        return _payload(code, err.description or err.name), err.code or 500

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("Unhandled error")
        return _payload("internal_error", "Unexpected server error."), 500

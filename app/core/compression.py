"""gzip for large JSON bodies (a week of GPS points shrinks about 10x)."""
import gzip

from flask import Flask, Response, current_app, request


def register_gzip(app: Flask) -> None:
    @app.after_request
    def gzip_response(resp: Response) -> Response:
        if resp.status_code != 200 or resp.direct_passthrough or "Content-Encoding" in resp.headers:
            return resp
        if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
            return resp
        data = resp.get_data()
        if len(data) < current_app.config["SETTINGS"].gzip_min_bytes:
            return resp
        resp.set_data(gzip.compress(data, compresslevel=5))
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers.add("Vary", "Accept-Encoding")
        return resp

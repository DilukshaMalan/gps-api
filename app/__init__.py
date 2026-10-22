from flask import Flask

from app.config import Settings
from app.core.compression import register_gzip
from app.core.errors import register_error_handlers
from app.core.security import register_api_key_check
from app.routes import health, vehicles
from app.services.telemetry_service import TelemetryService


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings()
    app = Flask(__name__)
    app.json.sort_keys = False
    app.config["SETTINGS"] = settings
    app.extensions["telemetry"] = TelemetryService(settings.data_dir)   # loads the JSON files once

    register_error_handlers(app)
    register_api_key_check(app)
    register_gzip(app)
    app.register_blueprint(health.bp)
    app.register_blueprint(vehicles.bp)
    return app

from flask import Blueprint, current_app

from app.models.telemetry import Health

bp = Blueprint("health", __name__, url_prefix="/api/v1")


@bp.get("/health")
def health():
    count = current_app.extensions["telemetry"].vehicle_count
    return Health(status="ok", vehicles=count).model_dump_json(), 200, {"Content-Type": "application/json"}

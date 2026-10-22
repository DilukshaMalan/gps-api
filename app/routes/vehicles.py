"""The GPS endpoints.

    GET /api/v1/vehicles                                     (optional) list vehicles + data range
    GET /api/v1/vehicles/{vehicleId}/position                1. latest position
    GET /api/v1/vehicles/{vehicleId}/trips?from=&to=         2. trip summaries in a window
        ...&includePoints=true[&maxPoints=5000]              3. same, with GPS points
    GET /api/v1/vehicles/{vehicleId}/trips/{tripId}          4. one trip with its points
"""
from datetime import timedelta

from flask import Blueprint, Response, current_app, request
from pydantic import BaseModel

from app.core.errors import ApiError
from app.core.timeparse import parse_bool, parse_instant, parse_max_points
from app.models.telemetry import VehicleList
from app.services.telemetry_service import TelemetryService

bp = Blueprint("vehicles", __name__, url_prefix="/api/v1/vehicles")


def _service() -> TelemetryService:
    return current_app.extensions["telemetry"]


def _json(model: BaseModel, cacheable: bool = False) -> Response:
    # exclude_unset: `points` is left out of summaries, but a null `endReason` is kept.
    resp = Response(model.model_dump_json(exclude_unset=True), mimetype="application/json")
    if cacheable:                    # ETag lets the app send If-None-Match and get a tiny 304
        resp.add_etag()
        resp = resp.make_conditional(request)
    return resp


@bp.get("")
def list_vehicles():
    return _json(VehicleList(vehicles=_service().list_vehicles()))


@bp.get("/<vehicle_id>/position")
def position(vehicle_id: str):
    return _json(_service().get_position(vehicle_id))


@bp.get("/<vehicle_id>/trips")
def trips(vehicle_id: str):
    start = parse_instant(request.args.get("from"), "from")
    end = parse_instant(request.args.get("to"), "to")
    if end < start:
        raise ApiError(400, "invalid_range", "'to' must not be earlier than 'from'.")
    max_days = current_app.config["SETTINGS"].max_range_days
    if end - start > timedelta(days=max_days):
        raise ApiError(400, "range_too_large", f"The requested window is longer than {max_days} days.")
    include_points = parse_bool(request.args.get("includePoints"), "includePoints")
    max_points = parse_max_points(request.args.get("maxPoints"))
    return _json(_service().get_trips(vehicle_id, start, end, include_points, max_points), cacheable=True)


@bp.get("/<vehicle_id>/trips/<trip_id>")
def trip_detail(vehicle_id: str, trip_id: str):
    max_points = parse_max_points(request.args.get("maxPoints"))
    return _json(_service().get_trip(vehicle_id, trip_id, max_points), cacheable=True)

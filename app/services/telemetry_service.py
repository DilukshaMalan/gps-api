"""Loads the GPS files once at start-up and answers queries from memory.

No web-framework code in here, so the same service works unchanged under Flask, FastAPI, etc.
Replace the file loading with a database later and keep the public methods as they are.
"""
import json
import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.errors import NotFoundError
from app.models.telemetry import (LastKnown, Point, Position, Trip, TripsMeta, TripsResponse,
                                  VehicleInfo)


@dataclass
class _TripRecord:
    summary: Trip                 # `points` deliberately left unset
    points: list[Point]
    epochs: list[float]           # point timestamps as epoch seconds, for fast window slicing
    start: float
    end: float


@dataclass
class _VehicleRecord:
    vehicle_id: str
    data_source: str
    interval_s: int
    trips: list[_TripRecord]      # oldest first


def _thin(points: list[Point], stride: int) -> list[Point]:
    """Keep every `stride`-th point, always keeping the last one."""
    if stride <= 1 or len(points) <= 2:
        return points
    out = points[::stride]
    if out[-1] is not points[-1]:
        out.append(points[-1])
    return out


class TelemetryService:
    def __init__(self, data_dir: Path) -> None:
        self._vehicles: dict[str, _VehicleRecord] = {}
        files = sorted(Path(data_dir).glob("*_trips.json"))
        if not files:
            raise RuntimeError(f"No *_trips.json files found in {data_dir}")
        for file in files:
            record = self._load(file)
            self._vehicles[record.vehicle_id] = record

    # ───────────────────────── loading ─────────────────────────
    @staticmethod
    def _load(file: Path) -> _VehicleRecord:
        raw = json.loads(file.read_text(encoding="utf-8"))
        trips: list[_TripRecord] = []
        for t in raw["trips"]:
            pts = [Point(**p) for p in t.pop("points")]
            summary = Trip(**t)
            trips.append(_TripRecord(summary=summary, points=pts,
                                     epochs=[p.timestamp.timestamp() for p in pts],
                                     start=summary.startTime.timestamp(),
                                     end=summary.endTime.timestamp()))
        trips.sort(key=lambda r: r.start)
        meta = raw.get("meta", {})
        return _VehicleRecord(vehicle_id=raw["vehicleId"],
                              data_source=meta.get("dataSource", "unknown"),
                              interval_s=int(meta.get("samplingIntervalSeconds", 5)),
                              trips=trips)

    def _vehicle(self, vehicle_id: str) -> _VehicleRecord:
        try:
            return self._vehicles[vehicle_id]
        except KeyError:
            raise NotFoundError("vehicle_not_found", f"Unknown vehicle '{vehicle_id}'.")

    # ───────────────────────── queries ─────────────────────────
    @property
    def vehicle_count(self) -> int:
        return len(self._vehicles)

    def list_vehicles(self) -> list[VehicleInfo]:
        out = []
        for v in sorted(self._vehicles.values(), key=lambda x: x.vehicle_id):
            last = v.trips[-1].points[-1]
            out.append(VehicleInfo(
                vehicleId=v.vehicle_id,
                dataStart=v.trips[0].summary.startTime,
                dataEnd=last.timestamp,
                tripCount=len(v.trips),
                pointCount=sum(len(t.points) for t in v.trips),
                lastKnown=LastKnown(**last.model_dump())))
        return out

    def get_position(self, vehicle_id: str) -> Position:
        last = self._vehicle(vehicle_id).trips[-1].points[-1]
        return Position(vehicleId=vehicle_id, **last.model_dump())

    def get_trips(self, vehicle_id: str, start: datetime, end: datetime,
                  include_points: bool, max_points: int | None) -> TripsResponse:
        """Trips that overlap [start, end]. With points, they are clipped to that window."""
        v = self._vehicle(vehicle_id)
        lo_t, hi_t = start.timestamp(), end.timestamp()
        hits = [r for r in v.trips if r.start <= hi_t and r.end >= lo_t]

        if not include_points:
            return TripsResponse(
                vehicleId=vehicle_id,
                meta=TripsMeta(dataSource=v.data_source, samplingIntervalSeconds=v.interval_s,
                               tripCount=len(hits)),
                trips=[r.summary for r in hits])

        clipped: list[tuple[_TripRecord, list[Point]]] = []
        for r in hits:
            pts = r.points[bisect_left(r.epochs, lo_t):bisect_right(r.epochs, hi_t)]
            if pts:                                   # a trip with no samples in the window is skipped
                clipped.append((r, pts))

        total = sum(len(p) for _, p in clipped)
        stride = math.ceil(total / max_points) if max_points and total > max_points else 1
        trips, point_count = [], 0
        for r, pts in clipped:
            pts = _thin(pts, stride)
            point_count += len(pts)
            trips.append(r.summary.model_copy(update={"points": pts}))
        return TripsResponse(
            vehicleId=vehicle_id,
            meta=TripsMeta(dataSource=v.data_source, samplingIntervalSeconds=v.interval_s,
                           tripCount=len(trips), pointCount=point_count,
                           effectiveIntervalSeconds=v.interval_s * stride),
            trips=trips)

    def get_trip(self, vehicle_id: str, trip_id: str, max_points: int | None) -> Trip:
        v = self._vehicle(vehicle_id)
        for r in v.trips:
            if r.summary.tripId == trip_id:
                stride = math.ceil(len(r.points) / max_points) if max_points and len(r.points) > max_points else 1
                return r.summary.model_copy(update={"points": _thin(r.points, stride)})
        raise NotFoundError("trip_not_found", f"Vehicle '{vehicle_id}' has no trip '{trip_id}'.")

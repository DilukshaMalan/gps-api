"""Response models. Field names are camelCase on purpose: they are the exact JSON keys the iOS
app's Codable models (TelemetryPoint, TelemetryTrip) already decode."""
from datetime import datetime

from pydantic import BaseModel


class Point(BaseModel):
    timestamp: datetime
    latitude: float
    longitude: float
    speedKmh: float
    engineOn: bool


class Trip(BaseModel):
    """One engine-on -> engine-off journey. `points` is only present when requested."""
    tripId: str
    startTime: datetime
    endTime: datetime
    startReason: str
    endReason: str | None          # null while the trip is still in progress
    distanceKm: float
    maxSpeedKmh: float
    averageSpeedKmh: float
    points: list[Point] | None = None


class TripsMeta(BaseModel):
    dataSource: str
    samplingIntervalSeconds: int
    tripCount: int
    pointCount: int | None = None              # only when points are included
    effectiveIntervalSeconds: int | None = None  # > samplingIntervalSeconds when downsampled


class TripsResponse(BaseModel):
    vehicleId: str
    meta: TripsMeta
    trips: list[Trip]


class Position(BaseModel):
    vehicleId: str
    timestamp: datetime
    latitude: float
    longitude: float
    speedKmh: float
    engineOn: bool


class LastKnown(BaseModel):
    timestamp: datetime
    latitude: float
    longitude: float
    speedKmh: float
    engineOn: bool


class VehicleInfo(BaseModel):
    vehicleId: str
    dataStart: datetime
    dataEnd: datetime
    tripCount: int
    pointCount: int
    lastKnown: LastKnown


class VehicleList(BaseModel):
    vehicles: list[VehicleInfo]


class Health(BaseModel):
    status: str
    vehicles: int

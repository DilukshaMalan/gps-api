# GPS API (QuickRentCar tracking service)

Read-only service that exposes GPS trips and positions. It knows nothing about rentals, bookings or
package distance — the iOS app / your own backend combines those with this data.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -r requirements.txt
python run.py                                           # http://localhost:8000
python -m unittest discover -s tests -v                 # 19 tests
```

Optional settings (environment variables, see `.env.example`): `GPS_API_KEY` (turns on the
`X-API-Key` header check), `GPS_DATA_DIR`, `GPS_MAX_RANGE_DAYS` (default 31).

## Data files

Put the generated files in `data/`:

```
data/QR-001_trips.json
data/QR-002_trips.json
data/QR-003_trips.json
```

Every `*_trips.json` found there becomes a vehicle (its `vehicleId` is the id used in URLs). They are
loaded into memory once at start-up, so restart after replacing a file. `vehicles_index.json` is not
read — the API derives the same information from the trip files.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /api/v1/vehicles/{vehicleId}/position` | Latest position, speed and engine state |
| `GET /api/v1/vehicles/{vehicleId}/trips?from=&to=` | Trip summaries overlapping the window |
| `GET /api/v1/vehicles/{vehicleId}/trips?from=&to=&includePoints=true&maxPoints=5000` | Same trips with GPS points clipped to the window; `maxPoints` thins them (the last point is always kept) |
| `GET /api/v1/vehicles/{vehicleId}/trips/{tripId}?maxPoints=` | One trip with its points |
| `GET /api/v1/vehicles` | Vehicles with data range and last position |
| `GET /api/v1/health` | Liveness check (never needs the API key) |

Rules: `from` and `to` are ISO 8601 **with an offset**, e.g. `2026-10-14T00:00:00+05:30`; `to` must not
be before `from`; the window may be at most 31 days; `maxPoints` is 50–50000. Errors always look like
`{"error": {"code": "...", "message": "..."}}` with 400, 401 or 404.

A `+` in a URL must be sent as `%2B`. If a client forgets, the API repairs it, but encode it properly.

```bash
curl "http://localhost:8000/api/v1/vehicles/QR-001/position"
curl "http://localhost:8000/api/v1/vehicles/QR-001/trips?from=2026-10-16T00:00:00%2B05:30&to=2026-10-16T23:59:59%2B05:30"
curl -H "Accept-Encoding: gzip" --compressed \
  "http://localhost:8000/api/v1/vehicles/QR-003/trips?from=2026-10-12T00:00:00%2B05:30&to=2026-10-18T23:59:59%2B05:30&includePoints=true&maxPoints=5000"
```

Responses over 1 KB are gzip-compressed when the client sends `Accept-Encoding: gzip` (URLSession does
this automatically), and trip responses carry an `ETag` so a repeat request can return `304`.

## Layout

```
app/__init__.py              create_app(): wires everything together
app/config.py                settings from environment variables
app/models/telemetry.py      Pydantic response models (the JSON contract)
app/services/telemetry_service.py   loads the JSON files, window clipping, downsampling
app/routes/vehicles.py       the endpoints above
app/routes/health.py         /health
app/core/                    errors, API key check, gzip, query-parameter parsing
data/                        the *_trips.json files
tests/test_api.py            tests
run.py                       development entry point
```

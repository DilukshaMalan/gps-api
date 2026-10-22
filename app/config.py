"""Runtime settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        # Folder that holds the QR-00X_trips.json files.
        self.data_dir = Path(os.environ.get("GPS_DATA_DIR", BASE_DIR / "data"))
        # When set, every /api/v1 request except /health must send  X-API-Key: <value>.
        self.api_key = os.environ.get("GPS_API_KEY") or None
        # Largest allowed (to - from) window for the trips endpoint.
        self.max_range_days = int(os.environ.get("GPS_MAX_RANGE_DAYS", "31"))
        # Responses smaller than this are not gzip-compressed.
        self.gzip_min_bytes = int(os.environ.get("GPS_GZIP_MIN_BYTES", "1000"))

"""Run:  python -m unittest discover -s tests -v   (from the gps-api folder)"""
import gzip
import json
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app          # noqa: E402
from app.config import Settings      # noqa: E402

DAY = "from=2026-10-16T00:00:00%2B05:30&to=2026-10-16T23:59:59%2B05:30"
WEEK = "from=2026-10-12T00:00:00%2B05:30&to=2026-10-18T23:59:59%2B05:30"


def raw(vehicle_id):
    return json.loads((ROOT / "data" / f"{vehicle_id}_trips.json").read_text())


def overlapping(vehicle_id, start, end):
    s, e = datetime.fromisoformat(start), datetime.fromisoformat(end)
    return [t for t in raw(vehicle_id)["trips"]
            if datetime.fromisoformat(t["startTime"]) <= e and datetime.fromisoformat(t["endTime"]) >= s]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app(Settings()).test_client()

    # ── health / list ──
    def test_health(self):
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok", "vehicles": 3})

    def test_list_vehicles(self):
        body = self.client.get("/api/v1/vehicles").get_json()
        self.assertEqual([v["vehicleId"] for v in body["vehicles"]], ["QR-001", "QR-002", "QR-003"])
        self.assertEqual(body["vehicles"][0]["tripCount"], 40)
        self.assertEqual(body["vehicles"][0]["lastKnown"]["engineOn"], False)

    # ── 1. position ──
    def test_position_parked(self):
        body = self.client.get("/api/v1/vehicles/QR-001/position").get_json()
        self.assertEqual(set(body), {"vehicleId", "timestamp", "latitude", "longitude", "speedKmh", "engineOn"})
        self.assertFalse(body["engineOn"])
        self.assertEqual(body["speedKmh"], 0.0)

    def test_position_moving_vehicle(self):
        body = self.client.get("/api/v1/vehicles/QR-002/position").get_json()
        self.assertTrue(body["engineOn"])
        self.assertGreater(body["speedKmh"], 0)

    def test_position_unknown_vehicle(self):
        r = self.client.get("/api/v1/vehicles/NOPE/position")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["error"]["code"], "vehicle_not_found")

    # ── 2. trip summaries ──
    def test_trip_summaries_one_day(self):
        body = self.client.get(f"/api/v1/vehicles/QR-003/trips?{DAY}").get_json()
        expected = overlapping("QR-003", "2026-10-16T00:00:00+05:30", "2026-10-16T23:59:59+05:30")
        self.assertEqual([t["tripId"] for t in body["trips"]], [t["tripId"] for t in expected])
        self.assertEqual(body["meta"]["tripCount"], len(expected))
        for t in body["trips"]:
            self.assertNotIn("points", t)
            self.assertIn("endReason", t)
            self.assertEqual(set(t), {"tripId", "startTime", "endTime", "startReason", "endReason",
                                      "distanceKm", "maxSpeedKmh", "averageSpeedKmh"})

    def test_in_progress_trip_keeps_null_end_reason(self):
        text = self.client.get("/api/v1/vehicles/QR-002/trips?from=2026-10-23T00:00:00%2B05:30"
                               "&to=2026-10-23T23:59:59%2B05:30").get_data(as_text=True)
        last = json.loads(text)["trips"][-1]
        self.assertIn("endReason", last)
        self.assertIsNone(last["endReason"])

    # ── 3. trips with points ──
    def test_points_are_clipped_to_window(self):
        url = (f"/api/v1/vehicles/QR-001/trips?from=2026-10-16T00:00:00%2B05:30"
               f"&to=2026-10-16T12:00:00%2B05:30&includePoints=true")
        body = self.client.get(url).get_json()
        limit = datetime.fromisoformat("2026-10-16T12:00:00+05:30")
        self.assertTrue(body["trips"])
        for t in body["trips"]:
            for p in t["points"]:
                self.assertLessEqual(datetime.fromisoformat(p["timestamp"]), limit)
        self.assertEqual(body["meta"]["pointCount"], sum(len(t["points"]) for t in body["trips"]))
        self.assertEqual(body["meta"]["effectiveIntervalSeconds"], 5)

    def test_full_week_points_match_source(self):
        body = self.client.get(f"/api/v1/vehicles/QR-001/trips?{WEEK}&includePoints=true").get_json()
        expected = overlapping("QR-001", "2026-10-12T00:00:00+05:30", "2026-10-18T23:59:59+05:30")
        self.assertEqual(len(body["trips"]), len(expected))
        got = sum(len(t["points"]) for t in body["trips"])
        want = sum(len(t["points"]) for t in expected)
        self.assertEqual(got, want)

    def test_max_points_downsamples_and_keeps_last_point(self):
        full = self.client.get(f"/api/v1/vehicles/QR-003/trips?{WEEK}&includePoints=true").get_json()
        thin = self.client.get(f"/api/v1/vehicles/QR-003/trips?{WEEK}&includePoints=true&maxPoints=2000").get_json()
        n_full = sum(len(t["points"]) for t in full["trips"])
        n_thin = sum(len(t["points"]) for t in thin["trips"])
        self.assertGreater(n_full, 2000)
        self.assertLess(n_thin, n_full)
        self.assertLessEqual(n_thin, 2000 + len(thin["trips"]))     # +1 kept last point per trip
        self.assertGreater(thin["meta"]["effectiveIntervalSeconds"], 5)
        for tf, tt in zip(full["trips"], thin["trips"]):
            self.assertEqual(tf["points"][-1], tt["points"][-1])
            self.assertEqual(tf["points"][0], tt["points"][0])

    # ── 4. trip detail ──
    def test_trip_detail(self):
        src = raw("QR-002")["trips"][3]
        body = self.client.get(f"/api/v1/vehicles/QR-002/trips/{src['tripId']}").get_json()
        self.assertEqual(body["tripId"], src["tripId"])
        self.assertEqual(len(body["points"]), len(src["points"]))
        self.assertEqual(body["points"][0], src["points"][0])

    def test_trip_detail_max_points(self):
        src = raw("QR-002")["trips"][3]
        body = self.client.get(f"/api/v1/vehicles/QR-002/trips/{src['tripId']}?maxPoints=100").get_json()
        self.assertLess(len(body["points"]), len(src["points"]))
        self.assertEqual(body["points"][-1], src["points"][-1])

    def test_trip_not_found(self):
        r = self.client.get("/api/v1/vehicles/QR-001/trips/QR001-TRIP-999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["error"]["code"], "trip_not_found")

    # ── validation ──
    def test_validation_errors(self):
        cases = {
            "/api/v1/vehicles/QR-001/trips": "invalid_request",                                    # missing from/to
            "/api/v1/vehicles/QR-001/trips?from=2026-10-16T00:00:00%2B05:30": "invalid_request",   # missing to
            "/api/v1/vehicles/QR-001/trips?from=2026-10-16T00:00:00&to=2026-10-17T00:00:00": "invalid_request",  # no offset
            "/api/v1/vehicles/QR-001/trips?from=yesterday&to=today": "invalid_request",
            "/api/v1/vehicles/QR-001/trips?from=2026-10-17T00:00:00%2B05:30&to=2026-10-16T00:00:00%2B05:30": "invalid_range",
            "/api/v1/vehicles/QR-001/trips?from=2026-08-01T00:00:00%2B05:30&to=2026-10-01T00:00:00%2B05:30": "range_too_large",
            f"/api/v1/vehicles/QR-001/trips?{DAY}&maxPoints=5": "invalid_request",
            f"/api/v1/vehicles/QR-001/trips?{DAY}&includePoints=maybe": "invalid_request",
        }
        for url, code in cases.items():
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.get_json()["error"]["code"], code)

    def test_unencoded_plus_in_offset_still_works(self):
        # a raw '+' arrives as a space; the API repairs it
        url = "/api/v1/vehicles/QR-001/trips?from=2026-10-16T00:00:00+05:30&to=2026-10-16T23:59:59+05:30"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()["trips"]),
                         len(overlapping("QR-001", "2026-10-16T00:00:00+05:30", "2026-10-16T23:59:59+05:30")))

    def test_unknown_route_uses_error_shape(self):
        r = self.client.get("/api/v1/nothing")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.get_json())

    # ── formatting / transport ──
    def test_timestamps_match_ios_iso8601_strategy(self):
        text = self.client.get(f"/api/v1/vehicles/QR-001/trips?{DAY}&includePoints=true").get_data(as_text=True)
        stamps = re.findall(r'"(?:timestamp|startTime|endTime)":"([^"]+)"', text)
        self.assertTrue(stamps)
        pattern = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+05:30$")      # offset, NO fractional seconds
        self.assertTrue(all(pattern.match(s) for s in stamps), [s for s in stamps if not pattern.match(s)][:3])

    def test_gzip_and_etag(self):
        url = f"/api/v1/vehicles/QR-003/trips?{WEEK}&includePoints=true"
        plain = self.client.get(url)
        zipped = self.client.get(url, headers={"Accept-Encoding": "gzip"})
        self.assertEqual(zipped.headers.get("Content-Encoding"), "gzip")
        self.assertLess(len(zipped.data), len(plain.data) / 5)
        self.assertEqual(json.loads(gzip.decompress(zipped.data)), plain.get_json())
        etag = plain.headers["ETag"]
        again = self.client.get(url, headers={"If-None-Match": etag})
        self.assertEqual(again.status_code, 304)


class ApiKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = Settings()
        s.api_key = "secret"
        cls.client = create_app(s).test_client()

    def test_key_required_except_health(self):
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
        r = self.client.get("/api/v1/vehicles/QR-001/position")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error"]["code"], "unauthorized")
        self.assertEqual(self.client.get("/api/v1/vehicles/QR-001/position",
                                         headers={"X-API-Key": "wrong"}).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/vehicles/QR-001/position",
                                         headers={"X-API-Key": "secret"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()

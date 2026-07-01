"""
Test for earthquake_plate_calculation task.
Verifies the closest earthquake to Pacific plate boundary within Pacific plate.
"""

import json
import os
import unittest


class TestEarthquakeTask(unittest.TestCase):
    EXPECTED_RESULT = {
        "id": "us6000m27f",
        "place": "southern East Pacific Rise",
        "time": "2024-01-06T12:33:02Z",
        "magnitude": 5.5,
        "latitude": -24.4019,
        "longitude": -116.0254,
        "distance_km": 0.12,
    }

    DISTANCE_TOLERANCE = 0.5
    COORD_TOLERANCE = 0.001
    MAG_TOLERANCE = 0.01

    result = None

    @classmethod
    def setUpClass(cls):
        paths = ["/root/answer.json", "answer.json"]
        path = None
        for p in paths:
            if os.path.exists(p):
                path = p
                break
        if path is None:
            raise FileNotFoundError("Answer file not found. Expected /root/answer.json")
        with open(path, encoding="utf-8") as f:
            cls.result = json.load(f)

    def test_output_file_and_structure(self):
        required_fields = ["id", "place", "time", "magnitude", "latitude", "longitude", "distance_km"]
        for field in required_fields:
            self.assertIn(field, self.result, f"Missing field: {field}")

    def test_earthquake_id(self):
        self.assertEqual(self.result.get("id"), self.EXPECTED_RESULT["id"],
            f"Wrong earthquake ID. Expected {self.EXPECTED_RESULT['id']}, got {self.result.get('id')}")

    def test_distance_km(self):
        computed = float(self.result.get("distance_km", 0))
        expected = self.EXPECTED_RESULT["distance_km"]
        self.assertAlmostEqual(computed, expected, delta=self.DISTANCE_TOLERANCE,
            msg=f"Distance mismatch. Expected {expected} ± {self.DISTANCE_TOLERANCE}, got {computed}")

    def test_magnitude(self):
        computed = float(self.result.get("magnitude", 0))
        expected = self.EXPECTED_RESULT["magnitude"]
        self.assertAlmostEqual(computed, expected, delta=self.MAG_TOLERANCE)

    def test_coordinates(self):
        lat = float(self.result.get("latitude", 0))
        lon = float(self.result.get("longitude", 0))
        self.assertAlmostEqual(lat, self.EXPECTED_RESULT["latitude"], delta=self.COORD_TOLERANCE)
        self.assertAlmostEqual(lon, self.EXPECTED_RESULT["longitude"], delta=self.COORD_TOLERANCE)

    def test_time_format(self):
        time_str = self.result.get("time", "")
        self.assertRegex(time_str, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


if __name__ == "__main__":
    unittest.main(verbosity=2)

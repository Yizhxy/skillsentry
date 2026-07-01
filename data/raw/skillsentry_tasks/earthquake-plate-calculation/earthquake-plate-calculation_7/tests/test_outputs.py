"""
Test for earthquake_plate_calculation task.

Verifies the agent computed the correct information for the 2024 earthquake
within the target plate based on the specified metric (farthest).
"""

import json
import os
import unittest


class TestEarthquakeTask(unittest.TestCase):
    EXPECTED_RESULT = {
        "id": "us7000mqp4",
        "place": "Sea of Okhotsk",
        "time": "2024-06-06T11:07:53Z",
        "magnitude": 5.9,
        "latitude": 50.1126,
        "longitude": 147.684,
        "distance_km": 563.88,
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
        self.assertAlmostEqual(computed, expected, delta=self.MAG_TOLERANCE,
            msg=f"Magnitude mismatch. Expected {expected}, got {computed}")

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

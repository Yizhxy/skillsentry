"""
Test for econ_detrending_correlation task.

Verifies the agent computed the correct correlation coefficient between
detrended (HP-filtered, lambda=100) real PCE and real PFI for 1990-2024.
"""

import os
import unittest


class TestEconomicsTask(unittest.TestCase):
    EXPECTED_CORRELATION = 0.71132
    TOLERANCE = 0.001

    def get_answer_path(self):
        for path in ["/root/answer.txt", "answer.txt"]:
            if os.path.exists(path):
                return path
        return None

    def test_answer_file_exists(self):
        self.assertIsNotNone(self.get_answer_path(), "Answer file not found. Expected /root/answer.txt")

    def test_answer_is_valid_number(self):
        path = self.get_answer_path()
        if path is None:
            self.skipTest("Answer file not found")
        with open(path) as f:
            content = f.read().strip()
        try:
            float(content)
        except ValueError:
            self.fail(f"Answer '{content}' is not a valid number")

    def test_correlation_value_correct(self):
        path = self.get_answer_path()
        if path is None:
            self.skipTest("Answer file not found")
        with open(path) as f:
            content = f.read().strip()
        try:
            computed = float(content)
        except ValueError:
            self.fail(f"Answer '{content}' is not a valid number")
        self.assertAlmostEqual(
            computed, self.EXPECTED_CORRELATION, delta=self.TOLERANCE,
            msg=f"Correlation mismatch. Expected {self.EXPECTED_CORRELATION} ± {self.TOLERANCE}, got {computed}"
        )

    def test_answer_format(self):
        path = self.get_answer_path()
        if path is None:
            self.skipTest("Answer file not found")
        with open(path) as f:
            content = f.read().strip()
        self.assertNotIn("e", content.lower(), "Answer should not be in scientific notation")
        self.assertIn(".", content, "Answer should include decimal places")


if __name__ == "__main__":
    unittest.main(verbosity=2)

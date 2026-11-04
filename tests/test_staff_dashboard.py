import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
import staff_dashboard

class StaffConfigTests(unittest.TestCase):
    def test_short_secret_rejected(self):
        with patch.object(staff_dashboard, "TOKEN", "password"):
            with self.assertRaises(ValueError):
                staff_dashboard.require_token()

    def test_long_token_accepted(self):
        with patch.object(staff_dashboard, "TOKEN", "x" * 48):
            staff_dashboard.require_token()

    def test_unsafe_bind_rejected(self):
        with patch.object(staff_dashboard, "TOKEN", "x" * 48), patch.object(staff_dashboard, "HOST", "8.8.8.8"):
            with self.assertRaises(ValueError):
                staff_dashboard.require_token()

if __name__ == "__main__":
    unittest.main()

import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_vps_env import validate

class VpsTests(unittest.TestCase):
    def test_vpn_addresses(self):
        for ip in ("10.50.1.3", "100.101.22.33", "192.168.1.10"):
            self.assertTrue(validate({"CDR_VPN_IP": ip, "CDR_STAFF_TOKEN": "A12b34C56d78E90fGhIjKlMnOpQrStUvWxYz", "CDR_REGISTRATION_KEY": "1Qaz2Wsx3Edc4Rfv5Tgb6Yhn7Ujm8Ik9"}))
    def test_public_refused(self):
        for ip in ("8.8.8.8", "0.0.0.0", "127.0.0.1", "169.254.0.5"):
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                validate({"CDR_VPN_IP": ip, "CDR_STAFF_TOKEN": "A12b34C56d78E90fGhIjKlMnOpQrStUvWxYz"})
    def test_placeholder_refused(self):
        with self.assertRaises(ValueError):
            validate({"CDR_VPN_IP": "100.101.22.33", "CDR_STAFF_TOKEN": "REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_CHARACTERS", "CDR_REGISTRATION_KEY": "1Qaz2Wsx3Edc4Rfv5Tgb6Yhn7Ujm8Ik9"})

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from offline_server import HTTP_FILES, LOGINLIST, ZONELIST


class AndroidDiscoveryTests(unittest.TestCase):
    def test_android_205761_request_paths(self):
        self.assertEqual(HTTP_FILES["loginlist_rel_na.txt"], LOGINLIST)
        self.assertEqual(HTTP_FILES["client_zonelist_rel_na.txt"], ZONELIST)

    def test_android_server_records_are_present(self):
        self.assertTrue(LOGINLIST.strip())
        self.assertTrue(ZONELIST.strip())


if __name__ == "__main__":
    unittest.main()

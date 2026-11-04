import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from offline_server import HTTP_FILES, LOGINLIST, ZONELIST


class AndroidDiscoveryTests(unittest.TestCase):
    def test_android_205761_request_paths(self):
        self.assertEqual(HTTP_FILES["loginlist_rel_na.txt"], LOGINLIST)
        self.assertEqual(HTTP_FILES["client_zonelist_rel_na.txt"], ZONELIST)

    def test_steam_zone_display_label_is_not_offline(self):
        self.assertEqual(HTTP_FILES["client_zonelist_rel_steam_na.txt"], ZONELIST)
        self.assertIn(" Reborn-Dev pc ", ZONELIST)
        self.assertNotIn(" Offline pc ", ZONELIST)
        self.assertTrue(ZONELIST.endswith("\n"))
        self.assertFalse(ZONELIST.endswith(r"\n"))

    def test_android_server_records_are_present(self):
        self.assertTrue(LOGINLIST.strip())
        self.assertTrue(ZONELIST.strip())


if __name__ == "__main__":
    unittest.main()

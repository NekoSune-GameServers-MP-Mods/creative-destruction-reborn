import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from nexproto import Protocol

class ProtocolLoaderTests(unittest.TestCase):
    def test_source_directory_does_not_execute_python(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "executed"
            (Path(td) / "evil_pto.py").write_text("open(%r,'w').write('EXECUTED')" % str(marker))
            with self.assertRaises(ValueError):
                Protocol(td)
            self.assertFalse(marker.exists())

if __name__ == "__main__":
    unittest.main()

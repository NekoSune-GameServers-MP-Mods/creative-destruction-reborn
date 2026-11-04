"""Regression tests for truncated fields and nested overrun cases from Codex static report."""
import os
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from nexproto import unpack_fields, gen_tag, pack_tag, unpack_value

class MalformedPacketTests(unittest.TestCase):
    def test_truncated_string_payload(self):
        desc = ((1, "VARSTR", "name"),)
        body = pack_tag(gen_tag(1, "VARSTR")) + struct.pack("<H", 10) + b"hi"
        with self.assertRaises(ValueError):
            unpack_fields(desc, body, 0, len(body))

    def test_truncated_optional_inside_parent(self):
        sub = ((1, "UINT8", "n"),)
        desc = ((1, "OPTIONAL", "opt", sub),)
        body = pack_tag(gen_tag(1, "OPTIONAL")) + struct.pack("<H", 6) + b"X"
        with self.assertRaises(ValueError):
            unpack_fields(desc, body, 0, len(body))

    def test_array_item_exceeds_container(self):
        sub = ((1, "UINT8", "n"),)
        desc = ((1, "ARRAY", "items", sub),)
        body = pack_tag(gen_tag(1, "ARRAY")) + struct.pack("<H", 4) + struct.pack("<H", 8) + b"XX"
        with self.assertRaises(ValueError):
            unpack_fields(desc, body, 0, len(body))

    def test_unknown_tag_length_overrun(self):
        desc = ()
        body = pack_tag(gen_tag(1, "VARSTR")) + struct.pack("<H", 200) + b"x"
        with self.assertRaises(ValueError):
            unpack_fields(desc, body, 0, len(body))

    def test_fixed_field_works(self):
        desc = ((1, "UINT16", "count"),)
        body = pack_tag(gen_tag(1, "UINT16")) + struct.pack("<H", 1234)
        self.assertEqual(unpack_fields(desc, body, 0, len(body)), {"count": 1234})

    def test_truncated_varint(self):
        with self.assertRaises(ValueError):
            unpack_value("VARINT", (), b"\x00", 0)

    def test_truncated_extended_tag(self):
        with self.assertRaises((ValueError, IndexError)):
            unpack_fields((), b"\x10", 0, 1)

if __name__ == "__main__":
    unittest.main()

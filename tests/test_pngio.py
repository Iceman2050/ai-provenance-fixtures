import hashlib
import unittest

from provenance_fixtures import pngio


def sample_pixels(width=8, height=4):
    out = bytearray()
    for y in range(height):
        for x in range(width):
            out.extend(((x * 31) % 256, (y * 57) % 256, ((x + y) * 13) % 256, 255))
    return bytes(out)


class PngIoTests(unittest.TestCase):
    def test_roundtrip_no_filter(self):
        pixels = sample_pixels()
        data = pngio.encode_png(8, 4, pixels)
        width, height, decoded, text = pngio.decode_png(data)
        self.assertEqual((width, height), (8, 4))
        self.assertEqual(decoded, pixels)
        self.assertEqual(text, {})

    def test_roundtrip_sub_filter_same_pixels_different_bytes(self):
        pixels = sample_pixels()
        plain = pngio.encode_png(8, 4, pixels, row_filter=0)
        subbed = pngio.encode_png(8, 4, pixels, row_filter=1)
        self.assertNotEqual(plain, subbed)
        _w, _h, decoded, _t = pngio.decode_png(subbed)
        self.assertEqual(decoded, pixels)

    def test_text_chunks_roundtrip_and_strip(self):
        pixels = sample_pixels()
        chunks = [("provenance.assertion.creator", "test"), ("provenance.payload_sha256", "ab" * 32)]
        data = pngio.encode_png(8, 4, pixels, chunks)
        _w, _h, _p, text = pngio.decode_png(data)
        self.assertEqual(text["provenance.assertion.creator"], "test")
        stripped = pngio.strip_text_chunks(data)
        _w, _h, decoded, text = pngio.decode_png(stripped)
        self.assertEqual(text, {})
        self.assertEqual(decoded, pixels)
        self.assertNotEqual(
            hashlib.sha256(stripped).hexdigest(), hashlib.sha256(data).hexdigest()
        )

    def test_resize_and_crop_are_deterministic(self):
        pixels = sample_pixels(8, 4)
        small = pngio.resize_nearest(8, 4, pixels, 4, 2)
        self.assertEqual(len(small), 4 * 2 * 4)
        self.assertEqual(small, pngio.resize_nearest(8, 4, pixels, 4, 2))
        w, h, cropped = pngio.crop_pixels(8, 4, pixels, (0, 0, 4, 2))
        self.assertEqual((w, h), (4, 2))
        self.assertEqual(len(cropped), 4 * 2 * 4)

    def test_rejects_non_png(self):
        with self.assertRaises(ValueError):
            pngio.decode_png(b"this is not a png")


if __name__ == "__main__":
    unittest.main()

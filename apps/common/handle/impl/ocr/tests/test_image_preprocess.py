# coding=utf-8
"""
    @project: maxkb
    @file: test_image_preprocess.py
    @desc: Unit tests for OCR image preprocessing.

    These tests are deliberately Django-free: image_preprocess only depends on
    Pillow + maxkb_logger, so they can run standalone with plain pytest/unittest.
"""
import unittest
from io import BytesIO

from common.handle.impl.ocr.image_preprocess import preprocess_for_ocr


def _make_png(size=(32, 24), color=128) -> bytes:
    """Build a tiny synthetic grayscale-ish PNG in memory."""
    from PIL import Image

    img = Image.new('RGB', size, (color, color, color))
    # paint a darker rectangle so autocontrast / thresholding have something
    # non-uniform to act on
    for x in range(4, 12):
        for y in range(4, 12):
            img.putpixel((x, y), (20, 20, 20))
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _is_valid_png(data: bytes) -> bool:
    """Confirm the bytes decode as a real image via Pillow."""
    from PIL import Image

    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
        return True
    except Exception:
        return False


class ImagePreprocessTest(unittest.TestCase):
    def setUp(self):
        self.png = _make_png()

    def test_all_levels_return_valid_png(self):
        for level in ('off', 'standard', 'aggressive'):
            out = preprocess_for_ocr(self.png, level=level)
            self.assertTrue(
                _is_valid_png(out),
                msg=f"level={level!r} did not return valid image bytes",
            )

    def test_off_returns_input_unchanged(self):
        out = preprocess_for_ocr(self.png, level='off')
        self.assertIs(out, self.png)

    def test_standard_actually_transforms(self):
        out = preprocess_for_ocr(self.png, level='standard')
        # standard does grayscale + autocontrast => bytes should differ from
        # the original RGB PNG
        self.assertNotEqual(out, self.png)
        self.assertTrue(_is_valid_png(out))

    def test_aggressive_returns_valid_png(self):
        out = preprocess_for_ocr(self.png, level='aggressive')
        self.assertTrue(_is_valid_png(out))
        self.assertNotEqual(out, self.png)

    def test_bad_input_bytes_return_input_no_raise(self):
        garbage = b'this is definitely not a png'
        for level in ('standard', 'aggressive'):
            # must not raise, and must fall back to the original bytes
            out = preprocess_for_ocr(garbage, level=level)
            self.assertEqual(out, garbage)

    def test_empty_input_returns_input(self):
        self.assertEqual(preprocess_for_ocr(b'', level='standard'), b'')

    def test_unknown_level_falls_back_safely(self):
        # an unrecognised level must not raise; current impl treats anything
        # that isn't 'off' as a preprocessing attempt and still yields a PNG
        out = preprocess_for_ocr(self.png, level='something-else')
        self.assertTrue(_is_valid_png(out))


if __name__ == '__main__':
    unittest.main()

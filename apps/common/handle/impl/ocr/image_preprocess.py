# coding=utf-8
"""
    @project: maxkb
    @file: image_preprocess.py
    @desc: Pre-process page images before sending to the OCR model.

    Scanned PDFs frequently carry watermarks, low contrast, and noise; a light
    preprocessing pass measurably improves vision-LLM transcription accuracy.

    Design: conservative. Grayscale + autocontrast is always safe. Aggressive
    binarization can destroy faint real text, so it's opt-in and gentle.
    On ANY failure we return the original bytes — preprocessing must never break OCR.
"""
from io import BytesIO

from common.utils.logger import maxkb_logger

__all__ = ['preprocess_for_ocr']

# Pixels brighter than this are treated as background / pale watermark and
# lifted to pure white in 'aggressive' mode. Kept high (200/255) on purpose so
# only genuinely pale pixels are touched — faint-but-real text usually sits
# well below this after autocontrast.
_WATERMARK_WHITE_THRESHOLD = 200
# Contrast bump for 'aggressive'. 1.4 is a gentle lift — strong enough to
# separate text from a washed-out background, mild enough not to crush
# anti-aliased strokes into noise.
_AGGRESSIVE_CONTRAST_FACTOR = 1.4


def preprocess_for_ocr(image_bytes: bytes, *, level: str = 'standard') -> bytes:
    """
    level:
      - 'off'       : return image_bytes unchanged
      - 'standard'  : grayscale + autocontrast (safe default, recommended)
      - 'aggressive': standard + gentle contrast enhance + light watermark
                      suppression (pale-pixel lift toward white)
    Returns PNG bytes. Never raises — on error logs a warning and returns the input.
    """
    if not image_bytes:
        return image_bytes
    if level == 'off':
        return image_bytes

    try:
        from PIL import Image, ImageEnhance, ImageOps

        with Image.open(BytesIO(image_bytes)) as src:
            # convert('L') => single-channel grayscale; drops colour watermarks
            # to a uniform plane and halves the byte size of the re-encoded PNG.
            img = src.convert('L')
            # cutoff=1 clips the lightest/darkest 1% before stretching — robust
            # against a few stray black/white speckles skewing the histogram.
            img = ImageOps.autocontrast(img, cutoff=1)

            if level == 'aggressive':
                img = ImageEnhance.Contrast(img).enhance(_AGGRESSIVE_CONTRAST_FACTOR)
                # Gentle watermark suppression: lift pale pixels to pure white.
                # NOT a hard binarization (no .convert('1')) — mid-grey real
                # text is left untouched so faint strokes survive.
                img = img.point(
                    lambda p: 255 if p > _WATERMARK_WHITE_THRESHOLD else p
                )

            out = BytesIO()
            img.save(out, format='PNG')
            return out.getvalue()
    except Exception as e:
        maxkb_logger.warning(
            f"OCR image preprocessing failed (level={level!r}); "
            f"falling back to original image bytes: {e}"
        )
        return image_bytes

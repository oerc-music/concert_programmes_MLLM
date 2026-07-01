"""
preprocess.py
=============
Image preparation: downscaling for upload, and binarisation for the
Original / Binarised view toggle in the results screen.

The binarisation algorithm (adaptive Gaussian thresholding, then convert to
1-bit) and its default constants are adapted unchanged from
`a_preprocess.py` in the archived research codebase, so a freshly binarised
user-supplied image looks consistent with the precomputed binarised samples
bundled in input/binarised/ (themselves taken directly from the paper's own
preprocessing, figshare `B_test_dataset`).

Unlike the archived pipeline, downscaling here is NOT driven by the OpenAI
Batch API's 200 MB file-size limit (this app makes synchronous calls, one
image at a time, so that constraint does not apply) -- the size below is
chosen for fast uploads and a crisp on-screen preview instead.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Union

import cv2
import numpy as np
from PIL import Image, ImageOps

# --- Sizing -------------------------------------------------------------
# Colour images sent to a provider (and the bundled input/*.jpg samples
# were produced at this same size).
SEND_COLOUR_MAX_LONG = 1600

# Binarisation bounds -- identical to the paper's CONFIG.json defaults
# (max_res_long / max_res_short), so on-the-fly binarisation of a
# user-supplied image matches the bundled input/binarised/ samples.
BINARISE_MAX_LONG = 2048
BINARISE_MIN_SHORT = 768
BINARISE_BLOCK_SIZE = 35
BINARISE_C = 15

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def _scale_factor(w: int, h: int, max_long: int, min_short: int | None) -> float:
    factors = [1.0, max_long / max(w, h)]
    if min_short is not None:
        factors.append(min_short / min(w, h))
    return min(factors)


def load_and_downscale(
    source: Union[Path, bytes, Image.Image],
    *,
    max_long: int,
    min_short: int | None = None,
) -> Image.Image:
    """Open an image (from a path, raw bytes, or an existing PIL Image),
    respect its EXIF orientation, and downscale -- never upscale -- so it
    fits within `max_long` (and `min_short`, if given)."""
    if isinstance(source, Image.Image):
        img = source
    elif isinstance(source, (bytes, bytearray)):
        img = Image.open(io.BytesIO(source))
    else:
        img = Image.open(source)

    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    w, h = img.size
    scale = _scale_factor(w, h, max_long, min_short)
    if scale < 1.0:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    return img


def binarise(
    img: Image.Image, *, block_size: int = BINARISE_BLOCK_SIZE, c: int = BINARISE_C
) -> Image.Image:
    """Adaptive Gaussian thresholding -> 1-bit image. Mirrors
    `a_preprocess.py`'s `_binarise()` in the archived pipeline exactly
    (same OpenCV call, same default constants)."""
    gray = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
    bw = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )
    return Image.fromarray(bw).convert("1")


def to_jpeg_bytes(img: Image.Image, *, quality: int = 87) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def prepare_send_bytes(path: Path, *, binarise_first: bool) -> tuple[bytes, str]:
    """Return (image_bytes, mime_type) ready to attach to a provider
    request, applying the setting chosen on the Setup screen ("send
    binarised" vs. the default colour)."""
    if binarise_first:
        img = load_and_downscale(path, max_long=BINARISE_MAX_LONG, min_short=BINARISE_MIN_SHORT)
        return to_png_bytes(binarise(img)), "image/png"
    img = load_and_downscale(path, max_long=SEND_COLOUR_MAX_LONG)
    return to_jpeg_bytes(img), "image/jpeg"

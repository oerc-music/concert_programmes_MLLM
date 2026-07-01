"""
mock.py
========
Offline / "no API key" demo mode: serves pre-computed annotations for the
100 bundled sample images instead of calling a live provider, so the whole
app -- progress bar, results browser, dynamic schema-driven fields,
downloads -- can be tried with no key, no network, and no quota. This is
the easiest way to verify the app is working, and is intended for use at
the DLfM 2026 conference itself.

mock_data.json was derived once (offline, not at runtime) from the archived
gpt-5-2025-08-07 majority-pick deliverable
(figshare_archive/experiment/F_final_deliverable), already normalised to
the exact shape of schema/oxford_schema.json via schema_adapters. It holds
a real, paper-reported result for these specific 100 images -- not a
synthetic placeholder -- but replaying it here calls no API and proves
nothing about a *current* model's live performance.
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "mock_data.json"
_cache: dict | None = None

MOCK_PROVIDER_NAME = "offline-demo"
MOCK_MODEL_NAME = "gpt-5-2025-08-07 (archived result, replayed offline)"


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return _cache


def available_stems() -> set[str]:
    """Image filename stems (no extension) this mode has data for."""
    return set(_load().keys())


def get_mock_annotation(stem: str) -> dict | None:
    """Return the pre-computed, canonical-shape annotation for `stem`
    (e.g. "IMG_7803"), or None if this image isn't one of the 100 bundled
    samples this mode covers."""
    return _load().get(stem)

"""
rate_limiter.py
================
Conservative, locally-enforced usage guards for the Google Gemini free
tier.

Google's own documentation does NOT publish fixed free-tier numbers for
requests-per-minute / requests-per-day -- it states these "depend on a
variety of factors (such as your usage tier) and can be viewed in Google
AI Studio" (https://aistudio.google.com/rate-limit), and that limits are
applied per *project*, not per API key.

Because of that, the constants below are deliberately conservative
defaults, NOT official Google figures. They are sized so a first-time user
on an untouched free-tier project can run the bundled 100-image sample
without tripping Google's own limits, while still leaving 429 handling
(see gemini_provider.py) to cover the rest. If your account's real tier
allows more, raise DEFAULT_MIN_INTERVAL_SECONDS / DEFAULT_DAILY_REQUEST_CAP
below -- check your actual limits at the AI Studio link above first.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .base import ProviderError

# --- Conservative defaults (NOT official Google figures -- see module docstring) ---
DEFAULT_MIN_INTERVAL_SECONDS = 4.0   # paces requests to roughly 15/minute
DEFAULT_DAILY_REQUEST_CAP = 250      # comfortably covers the 100-image sample, with margin

# Runtime usage counter -- recreated automatically, gitignored, never committed.
_USAGE_FILE = Path(__file__).resolve().parent.parent / ".gemini_usage.json"


@dataclass
class GeminiUsageStatus:
    used_today: int
    daily_cap: int
    min_interval_seconds: float

    @property
    def remaining_today(self) -> int:
        return max(0, self.daily_cap - self.used_today)


class GeminiRateLimiter:
    """Share one instance across a run (the server keeps a single instance
    for its lifetime) so pacing and the daily counter are enforced
    globally, not just within a single image loop."""

    def __init__(
        self,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        daily_cap: int = DEFAULT_DAILY_REQUEST_CAP,
        usage_file: Path = _USAGE_FILE,
    ):
        self.min_interval_seconds = min_interval_seconds
        self.daily_cap = daily_cap
        self._usage_file = usage_file
        self._lock = threading.Lock()
        self._last_request_at: float = 0.0

    @staticmethod
    def _today_key() -> str:
        return time.strftime("%Y-%m-%d")

    def _read_usage(self) -> dict:
        try:
            data = json.loads(self._usage_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        if data.get("date") != self._today_key():
            return {}  # new day -- counter resets
        return data

    def _write_usage(self, count: int) -> None:
        self._usage_file.write_text(
            json.dumps({"date": self._today_key(), "count": count}), encoding="utf-8"
        )

    def status(self) -> GeminiUsageStatus:
        """Used by GET /api/config so the Setup screen can show a live
        usage/pacing indicator before a run even starts."""
        with self._lock:
            used = self._read_usage().get("count", 0)
        return GeminiUsageStatus(used, self.daily_cap, self.min_interval_seconds)

    def before_request(self, model: str) -> None:
        """Block until it is safe to send the next request: enforces the
        daily cap (raises ProviderError if exhausted) and paces requests to
        roughly `min_interval_seconds` apart. `model` is accepted for
        future per-model limits but not currently used."""
        del model
        with self._lock:
            used = self._read_usage().get("count", 0)
            if used >= self.daily_cap:
                raise ProviderError(
                    f"Local Gemini free-tier guard reached ({used}/{self.daily_cap} "
                    "requests today). This is a conservative local limit, not "
                    "necessarily your actual Google quota -- see "
                    "src/providers/rate_limiter.py to raise it, or check your "
                    "real limits at https://aistudio.google.com/rate-limit."
                )
            elapsed = time.monotonic() - self._last_request_at
            wait = self.min_interval_seconds - elapsed
        if wait > 0:
            time.sleep(wait)

    def record_request(self, model: str) -> None:
        """Call once after a request succeeds (not before, and not on a
        retried/failed attempt)."""
        del model
        with self._lock:
            self._last_request_at = time.monotonic()
            used = self._read_usage().get("count", 0) + 1
            self._write_usage(used)

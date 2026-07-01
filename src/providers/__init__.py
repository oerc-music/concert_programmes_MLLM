"""Provider adapters for the GUI demo.

Each provider implements the `Provider` interface defined in `base.py` and
is otherwise independent -- annotate.py picks one by name and never branches
on provider elsewhere in the codebase.

This demo ships with a single live provider: Google Gemini (free tier).
"""

from .base import AnnotationResult, Provider, ProviderError
from .gemini_provider import GeminiProvider
from .rate_limiter import GeminiRateLimiter, GeminiUsageStatus

__all__ = [
    "AnnotationResult",
    "Provider",
    "ProviderError",
    "GeminiProvider",
    "GeminiRateLimiter",
    "GeminiUsageStatus",
]

"""
base.py
=======
The common interface the provider adapter (gemini_provider.py) implements,
and the small data classes used to pass results and errors back to the
orchestrator in annotate.py.

Both providers return an AnnotationResult holding the *raw* parsed JSON --
normalisation into the canonical, provider-indistinguishable shape happens
one layer up, in schema_adapters.normalise_response(), so this module knows
nothing about the schema itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class AnnotationResult:
    """The outcome of annotating a single image with a single provider call."""

    raw_text: str                      # the raw JSON text returned by the model
    parsed: dict                       # json.loads(raw_text), before normalisation
    provider: str                      # e.g. "gemini" or "mock"
    model: str
    usage: dict[str, Any] = field(default_factory=dict)  # token counts, for run_metadata.json


class ProviderError(RuntimeError):
    """Raised for any provider-side failure (missing/invalid key, rate limit
    exhausted, network error, malformed response). Messages are written to
    be safe to show directly in the UI -- never include the API key itself."""


class Provider(Protocol):
    """Structural interface implemented by GeminiProvider (and any future
    additions). annotate.py only depends on this shape."""

    name: str

    def annotate_image(
        self,
        *,
        image_bytes: bytes,
        image_mime: str,
        prompt_text: str,
        model: str,
        provider_schema: Any,
    ) -> AnnotationResult:
        """Send one image + prompt + (already-adapted) schema to the model
        and return its parsed JSON response. Raises ProviderError on
        failure; never returns a partially-parsed result."""
        ...

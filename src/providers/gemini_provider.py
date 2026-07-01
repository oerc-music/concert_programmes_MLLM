"""
gemini_provider.py
====================
Thin synchronous wrapper around Google's Gemini API (the stable
`client.models.generate_content` surface of the `google-genai` SDK) for
single-image, schema-constrained metadata extraction.

This demo runs on the Google Gemini free tier, which requires no payment
method and cannot incur charges. It directly realises the DLfM 2026
paper's own suggestion to test "providers beyond OpenAI (e.g., Anthropic,
Google)". Gemini was NOT evaluated in the paper itself; see
../../AI_DECLARATION.md and the main README for that caveat.

Because this is a free tier, every call is paced and capped by
GeminiRateLimiter (rate_limiter.py) BEFORE it is sent -- see that module
for why the limits there are conservative estimates, not official figures.
"""

from __future__ import annotations

import json
import time

from google import genai
from google.genai import types
from google.genai.errors import APIError

from .base import AnnotationResult, ProviderError
from .rate_limiter import GeminiRateLimiter

_MAX_RETRIES = 4
_BACKOFF_BASE_SECONDS = 4.0


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, rate_limiter: GeminiRateLimiter | None = None):
        if not api_key or not api_key.strip():
            raise ProviderError("No Google Gemini API key was provided.")
        self._client = genai.Client(api_key=api_key.strip())
        self._limiter = rate_limiter or GeminiRateLimiter()

    def annotate_image(
        self,
        *,
        image_bytes: bytes,
        image_mime: str,
        prompt_text: str,
        model: str,
        provider_schema: dict,
    ) -> AnnotationResult:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=provider_schema,
        )
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime),
            prompt_text,
        ]

        response = None
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            # Pace/cap EVERY attempt, including retries, against the free-tier guard.
            self._limiter.before_request(model)
            try:
                response = self._client.models.generate_content(
                    model=model, contents=contents, config=config
                )
                self._limiter.record_request(model)
                break
            except APIError as exc:
                self._limiter.record_request(model)  # the attempt still counts against quota
                if exc.code == 429:
                    last_error = exc
                    time.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                    continue
                raise ProviderError(f"Gemini request failed ({exc.code}): {exc.message}") from exc

        if response is None:
            raise ProviderError(f"Gemini rate limit exceeded after {_MAX_RETRIES} retries: {last_error}")

        raw_text = response.text or ""
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Gemini returned text that was not valid JSON: {exc}") from exc

        usage = {}
        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            usage = {
                "prompt_tokens": getattr(meta, "prompt_token_count", None),
                "completion_tokens": getattr(meta, "candidates_token_count", None),
                "total_tokens": getattr(meta, "total_token_count", None),
            }

        return AnnotationResult(
            raw_text=raw_text, parsed=parsed, provider=self.name, model=model, usage=usage
        )

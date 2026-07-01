"""
annotate.py
============
Run orchestration: discovers images, sends each one to the chosen provider
(or replays offline/mock data), writes the timestamped output folder, and
tracks live progress for the Setup -> Progress -> Results flow in the UI.

This REPLACES the archived pipeline's asynchronous Batch API state machine
(upload -> poll for up to 24h -> download, in run.py) with a synchronous
per-image loop run on a background thread, suited to an interactive GUI.
By default each image is sent once (n_variants=1); the optional N-variant
mode (majority-pick + agreement share, see schema_adapters.py) is a
schema-generic analogue of the archived pipeline's repeated-sampling idea.

Every result -- whichever provider produced it, including the offline mock
mode -- is normalised to the exact same canonical shape
(schema_adapters.normalise_response) before it is written anywhere, so the
per-image JSON, the JSONL, and the tidy CSV never reveal which provider ran.
"""

from __future__ import annotations

import csv
import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import mock
import preprocess
import schema_adapters as sa
from providers import GeminiProvider, GeminiRateLimiter, ProviderError


# ---------------------------------------------------------------------------
# Image discovery
# ---------------------------------------------------------------------------

def discover_images(input_dir: Path) -> list[Path]:
    """Every image directly in `input_dir` or any subfolder, EXCEPT a
    "binarised" subfolder (reserved for precomputed Original/Binarised
    companions -- see preprocess.py and input/README.md), sorted by path.
    Images should have unique filename stems; a stem collision across
    subfolders will overwrite an earlier result of the same name."""
    found = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or not preprocess.is_image_file(path):
            continue
        if "binarised" in path.relative_to(input_dir).parts[:-1]:
            continue
        found.append(path)
    return found


def _resolve_send_bytes(image_path: Path, input_dir: Path, *, send_binarised: bool) -> tuple[bytes, str]:
    """What actually gets attached to the provider request, honouring the
    Setup screen's "send binarised" setting. Prefers a precomputed
    Original/Binarised companion (input/binarised/<stem>.png) when one
    exists -- this is what makes the bundled 100 samples match the paper's
    own preprocessing exactly -- and falls back to live preprocessing
    (preprocess.py) for any other image."""
    if send_binarised:
        companion = input_dir / "binarised" / f"{image_path.stem}.png"
        if companion.exists():
            return companion.read_bytes(), "image/png"
    return preprocess.prepare_send_bytes(image_path, binarise_first=send_binarised)


# ---------------------------------------------------------------------------
# Tidy CSV flattening (one row per extracted value per image/concert/work/field)
# ---------------------------------------------------------------------------

def _flatten_object_fields(
    obj: dict, *, image: str, concert: int, work: int | str, shares: dict | None, rows: list[dict]
) -> None:
    """Emit rows for every scalar / list field directly on `obj` (NOT
    recursing into a nested "works" list -- the caller handles that as the
    next nesting level). Generic over field names, so it keeps working if
    the schema is edited; only the concert -> work two-level nesting
    convention is fixed by the tidy-format column layout."""
    for field_name, value in obj.items():
        if field_name == "works" or value is None:
            continue
        share_val = (shares or {}).get(field_name)
        if isinstance(value, list):
            item_shares = share_val if isinstance(share_val, list) else []
            for idx, item in enumerate(value, 1):
                if item is None:
                    continue
                item_value = str(item) if isinstance(item, dict) else item
                item_share = item_shares[idx - 1] if idx - 1 < len(item_shares) else None
                rows.append(
                    {
                        "image": image, "concert": concert, "work": work,
                        "field": f"{field_name}[{idx}]", "value": item_value, "share": item_share,
                    }
                )
        elif not isinstance(value, dict):  # scalar
            rows.append(
                {
                    "image": image, "concert": concert, "work": work,
                    "field": field_name, "value": value, "share": share_val,
                }
            )


def flatten_record(image: str, record: dict, *, shares: dict | None = None) -> list[dict]:
    """Turn one canonical-shape annotation into tidy rows -- one row per
    extracted value, columns (image, concert, work, field, value[, share]).
    `shares`, if given, is the parallel tree returned alongside the value
    by schema_adapters.majority_pick_with_shares()."""
    rows: list[dict] = []
    concerts = record.get("concerts") or []
    concert_shares = (shares or {}).get("concerts") or []
    for ci, concert in enumerate(concerts, 1):
        c_share = concert_shares[ci - 1] if ci - 1 < len(concert_shares) else None
        _flatten_object_fields(concert, image=image, concert=ci, work="", shares=c_share, rows=rows)
        works = concert.get("works") or []
        work_shares = (c_share or {}).get("works") or []
        for wi, work in enumerate(works, 1):
            w_share = work_shares[wi - 1] if wi - 1 < len(work_shares) else None
            _flatten_object_fields(work, image=image, concert=ci, work=wi, shares=w_share, rows=rows)
    return rows


# ---------------------------------------------------------------------------
# Run state (polled by GET /api/progress/{run_id})
# ---------------------------------------------------------------------------

@dataclass
class ImageStatus:
    stem: str
    filename: str
    state: str = "pending"  # pending | running | done | error | skipped
    error: str | None = None


@dataclass
class RunState:
    run_id: str
    provider: str
    model: str
    input_dir: str
    output_dir: str
    n_variants: int
    send_binarised: bool
    total: int
    images: list[ImageStatus] = field(default_factory=list)
    completed: int = 0
    started_at: str = ""
    finished_at: str | None = None
    cancelled: bool = False
    error: str | None = None  # run-level fatal error (e.g. bad key, before any image ran)

    def to_dict(self) -> dict:
        return {**asdict(self), "finished": self.finished_at is not None}


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Per-image annotation
# ---------------------------------------------------------------------------

def _annotate_one_image(
    *,
    image_path: Path,
    input_dir: Path,
    provider: Any,
    provider_name: str,
    provider_schema: Any,
    model: str,
    prompt_text: str,
    canonical_schema: dict,
    send_binarised: bool,
    n_variants: int,
) -> tuple[dict, dict | None, list[dict]]:
    """Returns (canonical_record, share_tree_or_None, usage_list)."""
    if provider_name == "mock":
        record = mock.get_mock_annotation(image_path.stem)
        if record is None:
            raise ProviderError(
                f'Offline demo mode has no pre-computed annotation for "{image_path.name}" -- '
                "it isn't one of the 100 bundled sample images. Switch to a live provider to "
                "annotate your own images, or point the input folder back at input/."
            )
        return record, None, []

    image_bytes, image_mime = _resolve_send_bytes(image_path, input_dir, send_binarised=send_binarised)

    normalised_variants: list[dict] = []
    usage_list: list[dict] = []
    for _ in range(max(1, n_variants)):
        result = provider.annotate_image(
            image_bytes=image_bytes,
            image_mime=image_mime,
            prompt_text=prompt_text,
            model=model,
            provider_schema=provider_schema,
        )
        normalised_variants.append(sa.normalise_response(result.parsed, canonical_schema))
        usage_list.append(result.usage)

    if n_variants <= 1:
        return normalised_variants[0], None, usage_list

    record, share_tree = sa.majority_pick_with_shares(normalised_variants, canonical_schema)
    return record, share_tree, usage_list


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict], *, include_share: bool) -> None:
    fieldnames = ["image", "concert", "work", "field", "value"] + (["share"] if include_share else [])
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in fieldnames}
            if "share" in out and isinstance(out["share"], float):
                out["share"] = round(out["share"], 4)
            writer.writerow(out)


def _write_run_metadata(
    run_dir: Path,
    state: RunState,
    *,
    finished_at: str,
    cancelled: bool,
    prompt_text: str,
    canonical_schema: dict,
) -> None:
    # `finished_at` / `cancelled` are passed explicitly rather than read off
    # `state` -- see the call site in _execute_run() for why: this file must
    # be fully written BEFORE state.finished_at is published to other
    # threads (the signal server.py polls to know it's safe to read results).
    meta = {
        "run_id": state.run_id,
        "provider": state.provider,
        "model": state.model,
        "started_at": state.started_at,
        "finished_at": finished_at,
        "cancelled": cancelled,
        "total_images": state.total,
        "completed_images": state.completed,
        "n_variants": state.n_variants,
        "send_binarised_to_model": state.send_binarised,
        "input_dir": state.input_dir,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "schema_sha256": hashlib.sha256(
            json.dumps(canonical_schema, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "errors": [{"image": s.filename, "error": s.error} for s in state.images if s.state == "error"],
    }
    if state.provider == "mock":
        meta["note"] = (
            "Offline demo mode: these are pre-computed archived results "
            "(figshare F_final_deliverable, gpt-5-2025-08-07), replayed with no live model "
            "call. See src/mock.py and AI_DECLARATION.md."
        )
    (run_dir / "run_metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Run execution (runs on a background thread)
# ---------------------------------------------------------------------------

def _execute_run(
    state: RunState,
    cancel_event: threading.Event,
    images: list[Path],
    input_dir: Path,
    run_dir: Path,
    *,
    provider_name: str,
    api_key: str | None,
    model: str,
    prompt_text: str,
    canonical_schema: dict,
    send_binarised: bool,
    n_variants: int,
    gemini_limiter: GeminiRateLimiter | None,
) -> None:
    provider: Any = None
    provider_schema: Any = None
    try:
        if provider_name == "gemini":
            provider = GeminiProvider(api_key, rate_limiter=gemini_limiter)
            provider_schema = sa.to_gemini_schema(canonical_schema)
        elif provider_name == "mock":
            pass
        else:
            raise ValueError(f"Unknown provider: {provider_name!r}")
    except (ProviderError, sa.SchemaError, ValueError) as exc:
        state.error = str(exc)
        for img in state.images:
            img.state = "error"
            img.error = "Run could not start -- see the run-level error above."
        finish_time = _now_iso()
        # Write the file BEFORE publishing state.finished_at (see
        # _write_run_metadata's docstring note) so a poller never observes
        # "finished" before run_metadata.json actually exists on disk.
        (run_dir / "run_metadata.json").write_text(
            json.dumps(
                {**state.to_dict(), "finished_at": finish_time, "fatal_error": str(exc)},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        state.finished_at = finish_time
        return

    jsonl_path = run_dir / "annotations.jsonl"
    csv_rows: list[dict] = []
    any_share = False

    with jsonl_path.open("w", encoding="utf-8") as jsonl_fh:
        for idx, image_path in enumerate(images):
            img_status = state.images[idx]

            if cancel_event.is_set():
                img_status.state = "skipped"
                img_status.error = "Run was stopped before this image."
                continue

            img_status.state = "running"
            _MAX_RETRIES = 10
            _last_exc: Exception | None = None
            for _attempt in range(_MAX_RETRIES):
                if cancel_event.is_set():
                    break
                try:
                    record, share_tree, _usage = _annotate_one_image(
                        image_path=image_path,
                        input_dir=input_dir,
                        provider=provider,
                        provider_name=provider_name,
                        provider_schema=provider_schema,
                        model=model,
                        prompt_text=prompt_text,
                        canonical_schema=canonical_schema,
                        send_binarised=send_binarised,
                        n_variants=n_variants,
                    )
                    _last_exc = None
                    break
                except Exception as exc:
                    _last_exc = exc
                    if _attempt < _MAX_RETRIES - 1 and not cancel_event.is_set():
                        _wait = min(30, 5 * (_attempt + 1))
                        img_status.error = (
                            f"Attempt {_attempt + 1}/{_MAX_RETRIES} failed — "
                            f"retrying in {_wait}s: {exc}"
                        )
                        time.sleep(_wait)

            if _last_exc is not None or cancel_event.is_set():
                img_status.state = "error"
                img_status.error = (
                    f"Failed after {_MAX_RETRIES} attempts: {_last_exc}"
                    if _last_exc is not None
                    else "Stopped before this image."
                )
                state.completed += 1
                continue

            (run_dir / f"{image_path.stem}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            jsonl_fh.write(json.dumps({image_path.stem: record}, ensure_ascii=False) + "\n")
            jsonl_fh.flush()

            rows = flatten_record(image_path.stem, record, shares=share_tree)
            csv_rows.extend(rows)
            if any(isinstance(r.get("share"), float) for r in rows):
                any_share = True

            img_status.state = "done"
            state.completed += 1

    finish_time = _now_iso()
    cancelled = cancel_event.is_set()
    # Write every output file BEFORE publishing state.finished_at, so a
    # poller (GET /api/progress) never observes "finished" while
    # annotations.csv / run_metadata.json are still being written.
    _write_csv(run_dir / "annotations.csv", csv_rows, include_share=any_share)
    _write_run_metadata(
        run_dir,
        state,
        finished_at=finish_time,
        cancelled=cancelled,
        prompt_text=prompt_text,
        canonical_schema=canonical_schema,
    )
    state.cancelled = cancelled
    state.finished_at = finish_time


# ---------------------------------------------------------------------------
# Public manager (used by server.py)
# ---------------------------------------------------------------------------

class RunManager:
    """Tracks runs in memory for live progress polling. Results themselves
    are read back from disk (run_dir), not from this in-memory state, so a
    server restart never loses completed work -- only the live progress
    view of a run still in flight."""

    def __init__(self) -> None:
        self._states: dict[str, RunState] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def start_run(
        self,
        *,
        provider_name: str,
        api_key: str | None,
        model: str,
        input_dir: Path,
        output_root: Path,
        prompt_text: str,
        canonical_schema: dict,
        send_binarised: bool = False,
        n_variants: int = 1,
        max_images: int | None = None,
        image_stems: list[str] | None = None,
        gemini_limiter: GeminiRateLimiter | None = None,
    ) -> str:
        images = discover_images(input_dir)
        if not images:
            raise ValueError(f"No images found in {input_dir}")
        if image_stems:
            # Specific images selected by the user — filter by stem, preserve order
            stem_set = set(image_stems)
            images = [p for p in images if p.stem in stem_set]
        elif max_images is not None:
            images = images[:max_images]
        if not images:
            raise ValueError("None of the selected images were found in the input folder.")

        with self._lock:
            run_id = time.strftime("%Y%m%d-%H%M%S")
            while run_id in self._states:  # guard against same-second collisions
                run_id += "-1"

        run_dir = output_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        state = RunState(
            run_id=run_id,
            provider=provider_name,
            model=model,
            input_dir=str(input_dir),
            output_dir=str(run_dir),
            n_variants=n_variants,
            send_binarised=send_binarised,
            total=len(images),
            images=[ImageStatus(stem=p.stem, filename=p.name) for p in images],
            started_at=_now_iso(),
        )
        cancel_event = threading.Event()
        with self._lock:
            self._states[run_id] = state
            self._cancel_events[run_id] = cancel_event

        thread = threading.Thread(
            target=_execute_run,
            args=(state, cancel_event, images, input_dir, run_dir),
            kwargs=dict(
                provider_name=provider_name,
                api_key=api_key,
                model=model,
                prompt_text=prompt_text,
                canonical_schema=canonical_schema,
                send_binarised=send_binarised,
                n_variants=n_variants,
                gemini_limiter=gemini_limiter,
            ),
            daemon=True,
            name=f"annotate-run-{run_id}",
        )
        thread.start()
        return run_id

    def get_state(self, run_id: str) -> RunState | None:
        with self._lock:
            return self._states.get(run_id)

    def cancel(self, run_id: str) -> bool:
        with self._lock:
            event = self._cancel_events.get(run_id)
        if event is None:
            return False
        event.set()
        return True

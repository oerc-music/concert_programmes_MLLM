"""
server.py
==========
FastAPI application for the GUI demo. This is a
LOCAL, single-user tool: it is meant to be started with
`python src/run_demo.py` and used from a browser on the same machine,
not deployed on a shared or public server. See README.md's
"Privacy and data handling" section before pointing it at anyone else's
material.

Endpoints are grouped below: static UI, prompt/schema editing, image
browsing, run lifecycle (start/progress/cancel/results), and downloads.
All business logic lives in the sibling modules (annotate.py, preprocess.py,
schema_adapters.py, mock.py, providers/) -- this file is deliberately thin:
it parses requests, resolves paths, and calls into them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

import annotate
import mock
import preprocess
import schema_adapters as sa
from providers import GeminiRateLimiter

# ---------------------------------------------------------------------------
# Paths and one-time setup
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = Path(__file__).resolve().parent / "web"

DEFAULT_INPUT_DIR = REPO_ROOT / "input"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"
PROMPT_PATH = REPO_ROOT / "prompts" / "PROMPT.txt"
SCHEMA_PATH = REPO_ROOT / "schema" / "oxford_schema.json"
load_dotenv(REPO_ROOT / ".env")  # local convenience only -- see .env.example

AVAILABLE_MODELS: dict[str, list[dict[str, str]]] = {
    "gemini": [
        {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite (free tier)"},
    ],
}
DEFAULT_MODEL = {"gemini": "gemini-3.1-flash-lite"}
ENV_VAR_FOR_PROVIDER = {"gemini": "GEMINI_API_KEY"}

run_manager = annotate.RunManager()
gemini_limiter = GeminiRateLimiter()

app = FastAPI(title="GUI Demo — MLLM-Assisted Concert Programme Metadata Extraction (DLfM 2026)")


# ---------------------------------------------------------------------------
# Path / key resolution helpers
# ---------------------------------------------------------------------------

def _resolve_path(raw: str | None, default: Path) -> Path:
    if not raw or not raw.strip():
        return default
    candidate = Path(raw.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate


def _resolve_api_key(provider: str, supplied: str | None) -> str | None:
    if supplied and supplied.strip():
        return supplied.strip()
    env_var = ENV_VAR_FOR_PROVIDER.get(provider)
    return os.environ.get(env_var) if env_var else None


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")


@app.get("/styles.css")
def styles_css() -> FileResponse:
    return FileResponse(WEB_DIR / "styles.css", media_type="text/css")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@app.get("/api/config")
def get_config() -> dict:
    gemini_status = gemini_limiter.status()
    return {
        "providers": ["gemini"],
        "default_provider": "gemini",
        "models": AVAILABLE_MODELS,
        "default_model": DEFAULT_MODEL,
        "env_key_present": {
            "gemini": bool(os.environ.get("GEMINI_API_KEY")),
        },
        "mock_available": True,
        "mock_image_count": len(mock.available_stems()),
        "default_input_dir": str(DEFAULT_INPUT_DIR.relative_to(REPO_ROOT)),
        "default_output_dir": str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)),
        "gemini_usage": {
            "used_today": gemini_status.used_today,
            "daily_cap": gemini_status.daily_cap,
            "remaining_today": gemini_status.remaining_today,
            "min_interval_seconds": gemini_status.min_interval_seconds,
            "note": (
                "These are conservative LOCAL guards, not official Google figures -- "
                "see src/providers/rate_limiter.py."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Prompt editor
# ---------------------------------------------------------------------------

@app.get("/api/prompt")
def get_prompt() -> dict:
    return {"text": PROMPT_PATH.read_text(encoding="utf-8")}


class TextBody(BaseModel):
    text: str


@app.post("/api/prompt")
def save_prompt(body: TextBody) -> dict:
    PROMPT_PATH.write_text(body.text, encoding="utf-8")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Schema editor
# ---------------------------------------------------------------------------

@app.get("/api/schema")
def get_schema() -> dict:
    return {"text": SCHEMA_PATH.read_text(encoding="utf-8")}


@app.post("/api/schema")
def save_schema(body: TextBody) -> dict:
    try:
        parsed = json.loads(body.text)
    except json.JSONDecodeError as exc:
        return JSONResponse({"ok": False, "problems": [f"Not valid JSON: {exc}"]}, status_code=400)

    problems = sa.validate_canonical(parsed)
    if problems:
        return JSONResponse({"ok": False, "problems": problems}, status_code=400)

    SCHEMA_PATH.write_text(body.text, encoding="utf-8")
    return {"ok": True, "problems": []}


# ---------------------------------------------------------------------------
# Image browsing (Setup screen thumbnails, and the results view's
# Original/Binarised toggle -- both go through this one resolver)
# ---------------------------------------------------------------------------

@app.get("/api/runs")
def list_runs(output_dir: str | None = None) -> dict:
    """Return all timestamped run folders that have a completed run_metadata.json,
    newest first. Used by the frontend to offer a run-picker on page load."""
    out = _resolve_path(output_dir, DEFAULT_OUTPUT_DIR)
    if not out.is_dir():
        return {"runs": []}
    runs: list[dict] = []
    for meta_path in sorted(out.glob("*/run_metadata.json"), reverse=True):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        runs.append({
            "run_id": meta.get("run_id"),
            "provider": meta.get("provider"),
            "model": meta.get("model", ""),
            "started_at": meta.get("started_at"),
            "finished_at": meta.get("finished_at"),
            "total_images": meta.get("total_images"),
            "completed_images": meta.get("completed_images"),
            "cancelled": meta.get("cancelled", False),
            "errors": len(meta.get("errors", [])),
        })
    return {"runs": runs}


@app.get("/api/images")
def list_images(dir: str | None = None) -> dict:
    input_dir = _resolve_path(dir, DEFAULT_INPUT_DIR)
    if not input_dir.is_dir():
        raise HTTPException(404, f"Folder not found: {input_dir}")
    images = annotate.discover_images(input_dir)
    return {
        "dir": str(input_dir),
        "count": len(images),
        "images": [{"stem": p.stem, "filename": p.name} for p in images],
    }


def _find_original(input_dir: Path, stem: str) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"):
        candidate = input_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    for path in sorted(input_dir.rglob(f"{stem}.*")):
        if not path.is_file() or not preprocess.is_image_file(path):
            continue
        if "binarised" in path.relative_to(input_dir).parts[:-1]:
            continue
        return path
    return None


@app.get("/api/image")
def get_image(dir: str, stem: str, view: str = "original") -> Response:
    input_dir = _resolve_path(dir, DEFAULT_INPUT_DIR)
    if view == "binarised":
        companion = input_dir / "binarised" / f"{stem}.png"
        if companion.exists():
            return Response(content=companion.read_bytes(), media_type="image/png")
        original = _find_original(input_dir, stem)
        if original is None:
            raise HTTPException(404, "Image not found")
        img = preprocess.load_and_downscale(
            original, max_long=preprocess.BINARISE_MAX_LONG, min_short=preprocess.BINARISE_MIN_SHORT
        )
        data = preprocess.to_png_bytes(preprocess.binarise(img))
        return Response(content=data, media_type="image/png")

    original = _find_original(input_dir, stem)
    if original is None:
        raise HTTPException(404, "Image not found")
    media_type = "image/png" if original.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(original, media_type=media_type)


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    provider: str  # "gemini" | "mock"
    api_key: str | None = None
    model: str | None = None
    input_dir: str | None = None   # defaults to bundled input/ folder
    output_dir: str | None = None  # defaults to output/; each run gets a timestamped subfolder
    send_binarised: bool = False
    n_variants: int = 1
    max_images: int | None = None  # fallback when image_stems is empty
    image_stems: list[str] | None = None  # specific stems to annotate (selection wins over max_images)


@app.post("/api/run")
def start_run(body: RunRequest) -> dict:
    if body.provider not in ("gemini", "mock"):
        raise HTTPException(400, f"Unknown provider: {body.provider!r}")

    input_dir = _resolve_path(body.input_dir, DEFAULT_INPUT_DIR)
    output_dir = _resolve_path(body.output_dir, DEFAULT_OUTPUT_DIR)
    if not input_dir.is_dir():
        raise HTTPException(400, f"Input folder not found: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    model = body.model or DEFAULT_MODEL.get(body.provider, "")
    if body.provider != "mock" and not model:
        raise HTTPException(400, "No model specified.")

    try:
        canonical_schema = sa.load_canonical_schema(SCHEMA_PATH)
    except sa.SchemaError as exc:
        raise HTTPException(400, f"schema/oxford_schema.json is invalid: {exc}") from exc
    problems = sa.validate_canonical(canonical_schema)
    if problems:
        raise HTTPException(400, "schema/oxford_schema.json has problems: " + "; ".join(problems))

    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    api_key = _resolve_api_key(body.provider, body.api_key)
    if body.provider != "mock" and not api_key:
        env_var = ENV_VAR_FOR_PROVIDER[body.provider]
        raise HTTPException(
            400,
            f"No API key supplied for {body.provider}, and {env_var} is not set in the environment.",
        )

    n_variants = max(1, min(10, body.n_variants))
    max_images = max(1, min(100, body.max_images)) if body.max_images is not None else None
    image_stems = [s for s in (body.image_stems or []) if s] or None

    try:
        run_id = run_manager.start_run(
            provider_name=body.provider,
            api_key=api_key,
            model=model,
            input_dir=input_dir,
            output_root=output_dir,
            prompt_text=prompt_text,
            canonical_schema=canonical_schema,
            send_binarised=body.send_binarised,
            n_variants=n_variants,
            max_images=max_images,
            image_stems=image_stems,
            gemini_limiter=gemini_limiter,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return {"run_id": run_id}


@app.get("/api/progress/{run_id}")
def get_progress(run_id: str) -> dict:
    state = run_manager.get_state(run_id)
    if state is not None:
        return state.to_dict()

    # Not in memory (e.g. server was restarted) -- fall back to the
    # persisted run_metadata.json, which is always written by the time a
    # run reaches "finished".
    meta_path = DEFAULT_OUTPUT_DIR / run_id / "run_metadata.json"
    if not meta_path.exists():
        # also check any custom output root used for this run -- scan once
        for candidate in _iter_output_roots():
            alt = candidate / run_id / "run_metadata.json"
            if alt.exists():
                meta_path = alt
                break
    if not meta_path.exists():
        raise HTTPException(404, f"Unknown run: {run_id}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return {
        "run_id": run_id,
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "total": meta.get("total_images"),
        "completed": meta.get("completed_images"),
        "finished_at": meta.get("finished_at"),
        "cancelled": meta.get("cancelled", False),
        "error": meta.get("fatal_error"),
        "images": [],
        "finished": True,
    }


def _iter_output_roots() -> list[Path]:
    """Best-effort discovery of output roots for restart-recovery lookups:
    the default output/ plus any sibling folders that look like they hold
    run subfolders. Kept deliberately simple -- this only matters if the
    server was restarted while a run_id is being polled by an old tab."""
    roots = [DEFAULT_OUTPUT_DIR]
    return [r for r in roots if r.is_dir()]


@app.post("/api/cancel/{run_id}")
def cancel_run(run_id: str) -> dict:
    ok = run_manager.cancel(run_id)
    if not ok:
        raise HTTPException(404, f"Unknown or already-finished run: {run_id}")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def _run_dir_for(run_id: str) -> Path:
    state = run_manager.get_state(run_id)
    if state is not None:
        return Path(state.output_dir)
    run_dir = DEFAULT_OUTPUT_DIR / run_id
    if run_dir.is_dir():
        return run_dir
    raise HTTPException(404, f"Unknown run: {run_id}")


@app.get("/api/results/{run_id}")
def get_results(run_id: str) -> dict:
    run_dir = _run_dir_for(run_id)
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        raise HTTPException(409, "This run has not finished yet.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    records: list[dict[str, Any]] = []
    for json_path in sorted(run_dir.glob("*.json")):
        if json_path.name == "run_metadata.json":
            continue
        try:
            record = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        records.append({"stem": json_path.stem, "record": record})

    return {"run_metadata": meta, "records": records}


@app.get("/api/results/{run_id}/download/csv")
def download_csv(run_id: str) -> FileResponse:
    run_dir = _run_dir_for(run_id)
    path = run_dir / "annotations.csv"
    if not path.exists():
        raise HTTPException(404, "No annotations.csv for this run.")
    return FileResponse(path, media_type="text/csv", filename=f"{run_id}_annotations.csv")


@app.get("/api/results/{run_id}/download/jsonl")
def download_jsonl(run_id: str) -> FileResponse:
    run_dir = _run_dir_for(run_id)
    path = run_dir / "annotations.jsonl"
    if not path.exists():
        raise HTTPException(404, "No annotations.jsonl for this run.")
    return FileResponse(path, media_type="application/jsonl", filename=f"{run_id}_annotations.jsonl")

"""
schema_adapters.py
===================
Translates the single, human-editable schema (schema/oxford_schema.json)
into the request-time dialect each provider expects, and normalises each
provider's raw JSON response back into one canonical shape -- so downstream
code (and the on-screen results) never has to know which provider produced
a given annotation.

Why two dialects are needed
----------------------------
- OpenAI's structured-output ("strict") JSON Schema mode requires every
  property to be listed in `required` (optionality is expressed only via a
  nullable union type, e.g. `anyOf: [{"type": "string"}, {"type": "null"}]`),
  forbids unknown keywords, and is happiest with a single flat schema.
- Google Gemini's `response_schema` (google-genai SDK,
  `types.GenerateContentConfig`) accepts a subset of the OpenAPI 3.0 schema
  object: UPPERCASE type names (STRING, INTEGER, OBJECT, ARRAY, BOOLEAN,
  NUMBER), no `anyOf` in the general case, and expresses optionality with a
  `"nullable": true` flag instead, with `required` listing only the keys
  that must genuinely be present.

Both translations are derived from the SAME canonical file, so editing that
one file changes what *both* providers are asked to extract, and -- via
`normalise_response` below -- both providers' answers are coerced back into
one identical Python shape before they ever reach the results view or the
CSV/JSONL writers.

Engineering note: two keywords used in the canonical file purely to
document intended cardinality for human readers (`minimum`, `minItems` --
"at least one concert/work") are deliberately NOT forwarded to either
provider's wire schema. Support for these keywords is inconsistent enough
across both APIs' structured-output modes that keeping them out is the more
reliable choice for a public demo; the "at least one" expectation is instead
stated directly in prompts/PROMPT.txt.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


class SchemaError(ValueError):
    """Raised when the user-editable schema file can't be parsed or translated
    into a provider's dialect. Messages are written to be shown directly to a
    non-programmer editing schema/oxford_schema.json."""


# JSON Schema (lowercase) type names -> Gemini's OpenAPI-subset (uppercase).
_GEMINI_TYPE_MAP = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "object": "OBJECT",
    "array": "ARRAY",
}

# Keywords carried over verbatim into both wire dialects.
_PASSTHROUGH_KEYS = ("description", "title")

# Canonical-only keywords stripped before sending a schema to either
# provider -- see module docstring.
_STRIP_KEYS = ("minimum", "maximum", "minItems", "maxItems")


def load_canonical_schema(path: Path) -> dict:
    """Load and parse the canonical oxford_schema.json, raising a
    SchemaError with a friendly message if it is missing or malformed."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SchemaError(f"Schema file not found: {path}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{path.name} is not valid JSON ({exc}).") from exc


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _resolve_refs(node: Any, defs: dict, _seen: tuple = ()) -> Any:
    """Recursively inline every "$ref" against `defs`, returning a fully
    self-contained schema fragment with no "$ref" left in it. Both provider
    dialects need a flat schema: Gemini's "$ref" support is documented only
    for self-referential/recursive structures (which this schema does not
    use), and inlining keeps both adapters on equally simple footing."""
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            name = ref.rsplit("/", 1)[-1]
            if name in _seen:
                raise SchemaError(
                    f'Unsupported recursive "$ref": {ref}. '
                    "This schema format does not support self-referencing definitions."
                )
            target = defs.get(name)
            if target is None:
                raise SchemaError(f'Unresolvable "$ref": {ref} (no matching entry in "$defs").')
            return _resolve_refs(target, defs, _seen + (name,))
        return {k: _resolve_refs(v, defs, _seen) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_resolve_refs(v, defs, _seen) for v in node]
    return node


def _flatten(canonical: dict) -> dict:
    defs = canonical.get("$defs", {})
    body = {k: v for k, v in canonical.items() if k != "$defs"}
    return _resolve_refs(body, defs)


def _split_nullable(node: dict) -> tuple[dict, bool]:
    """If `node` is `{"anyOf": [<T>, {"type": "null"}]}` (our convention for
    "optional"), return (<T merged with node's own title/description>, True).
    Otherwise return (node, False) unchanged."""
    any_of = node.get("anyOf")
    if isinstance(any_of, list) and len(any_of) == 2:
        types = [branch.get("type") for branch in any_of]
        if "null" in types:
            inner = next(branch for branch in any_of if branch.get("type") != "null")
            merged = dict(inner)
            for key in _PASSTHROUGH_KEYS:
                if key in node and key not in merged:
                    merged[key] = node[key]
            return merged, True
    return node, False


# ---------------------------------------------------------------------------
# Adapter: Gemini response_schema (OpenAPI 3.0 subset, UPPERCASE types)
# ---------------------------------------------------------------------------

def _gemini_node(node: dict) -> dict:
    inner, nullable = _split_nullable(node)
    inner = {k: v for k, v in inner.items() if k not in _STRIP_KEYS}
    node_type = inner.get("type")
    out: dict = {"type": _GEMINI_TYPE_MAP.get(node_type, "STRING")}

    if node_type == "object":
        props = inner.get("properties", {})
        out["properties"] = {key: _gemini_node(val) for key, val in props.items()}
        # Only genuinely-required keys go in "required" here; nullable
        # fields are marked individually via "nullable" below instead, so
        # the model may omit them or set them to null.
        required = [key for key, val in props.items() if not _split_nullable(val)[1]]
        if required:
            out["required"] = required
    elif node_type == "array":
        out["items"] = _gemini_node(inner["items"])

    if "enum" in inner:
        out["enum"] = inner["enum"]
    for key in _PASSTHROUGH_KEYS:
        if key in inner:
            out[key] = inner[key]
    if nullable:
        out["nullable"] = True
    return out


def to_gemini_schema(canonical: dict) -> dict:
    """Build the `response_schema` value for
    `types.GenerateContentConfig(response_mime_type="application/json", response_schema=...)`."""
    flat = _flatten(canonical)
    return _gemini_node(flat)


# ---------------------------------------------------------------------------
# Canonical normaliser -- both providers' raw JSON -> one identical shape
# ---------------------------------------------------------------------------

def _default_for(schema_node: dict) -> Any:
    inner, nullable = _split_nullable(schema_node)
    if nullable:
        return None
    node_type = inner.get("type")
    if node_type == "array":
        return []
    if node_type == "object":
        return {key: _default_for(val) for key, val in inner.get("properties", {}).items()}
    return None


def _coerce_scalar(value: Any, type_name: str | None) -> Any:
    if value is None or type_name is None:
        return value
    try:
        if type_name == "integer" and not isinstance(value, bool) and not isinstance(value, int):
            return int(value)
        if type_name == "number" and not isinstance(value, bool) and not isinstance(value, (int, float)):
            return float(value)
        if type_name == "string" and not isinstance(value, str):
            return str(value)
        if type_name == "boolean" and not isinstance(value, bool):
            return bool(value)
    except (TypeError, ValueError):
        return value
    return value


def _normalise_node(raw: Any, schema_node: dict) -> Any:
    inner, nullable = _split_nullable(schema_node)
    node_type = inner.get("type")

    if raw is None:
        return None if nullable else _default_for(schema_node)

    if node_type == "object":
        if not isinstance(raw, dict):
            return _default_for(schema_node)
        props = inner.get("properties", {})
        return {key: _normalise_node(raw.get(key), val) for key, val in props.items()}

    if node_type == "array":
        if not isinstance(raw, list):
            return []
        item_schema = inner["items"]
        return [_normalise_node(item, item_schema) for item in raw]

    return _coerce_scalar(raw, node_type)


def normalise_response(raw: Any, canonical: dict) -> dict:
    """Coerce a raw, already-`json.loads`-ed provider response into the
    exact shape of the canonical schema: same keys, same key order, same
    nesting, with missing optional fields filled in as null/[] -- regardless
    of which provider produced it. This is what makes OpenAI's and Gemini's
    output indistinguishable downstream (results view, CSV/JSONL, eval)."""
    flat = _flatten(canonical)
    return _normalise_node(raw if isinstance(raw, dict) else {}, flat)


# ---------------------------------------------------------------------------
# Majority pick (optional multi-variant / N-sample mode)
# ---------------------------------------------------------------------------
#
# This generalises d_calculate_variance_and_pick_majority.py's "modal
# value + agreement share" idea from the archived pipeline, but walks the
# CANONICAL SCHEMA generically rather than a hardcoded field list
# (CONCERT_SCALARS / WORK_SCALARS / ...). That keeps it working if the
# schema is edited (a field renamed, added, or removed), at the cost of
# being a little more abstract to read than the original.

def _value_key(value: Any) -> str:
    return "" if value is None else json.dumps(value, sort_keys=True)


def _modal_share(values: list[Any]) -> tuple[Any, float]:
    """Most frequent value in `values` (None counts as its own value) and
    its share of the total. Ties broken by first occurrence."""
    if not values:
        return None, 0.0
    counts = Counter(_value_key(v) for v in values)
    best_key, freq = counts.most_common(1)[0]
    best_value = next(v for v in values if _value_key(v) == best_key)
    return best_value, freq / len(values)


def _majority_node(records: list[Any], schema_node: dict) -> tuple[Any, Any]:
    """Returns (majority_value, share) for one schema position across N
    already-normalised records. `share` mirrors `majority_value`'s shape
    exactly: a dict of {field: share} for an object, a list of per-index
    shares for an array (each element itself shaped like its item type),
    and a float in [0, 1] at every scalar leaf."""
    inner, nullable = _split_nullable(schema_node)
    node_type = inner.get("type")

    if node_type == "object":
        props = inner.get("properties", {})
        value: dict = {}
        share: dict = {}
        for key, sub_schema in props.items():
            sub_records = [r.get(key) if isinstance(r, dict) else None for r in records]
            value[key], share[key] = _majority_node(sub_records, sub_schema)
        return value, share

    if node_type == "array":
        item_schema = inner["items"]
        lists = [r if isinstance(r, list) else [] for r in records]
        max_len = max((len(lst) for lst in lists), default=0)
        if max_len == 0:
            # No variant produced any items -- match normalise_response's
            # convention of null for an empty nullable list.
            return (None if nullable else []), (None if nullable else [])
        values: list = []
        shares: list = []
        for i in range(max_len):
            column = [lst[i] if i < len(lst) else None for lst in lists]
            v, s = _majority_node(column, item_schema)
            values.append(v)
            shares.append(s)
        return values, shares

    return _modal_share(records)


def majority_pick_with_shares(records: list[dict], canonical: dict) -> tuple[dict, dict]:
    """Given N already-normalised, identically-shaped records (one per
    repeated sample of the same image), return (majority_record,
    share_tree): one merged canonical record holding the per-field
    majority ("modal") value, and a parallel tree of the same shape giving
    each value's agreement share -- for the optional N-variant mode, as a
    schema-generic analogue of d_calculate_variance_and_pick_majority.py's
    "modal value + share" idea from the archived pipeline. annotate.py's
    flatten_record() walks `share_tree` alongside the record to attach a
    "share" column to the tidy CSV."""
    flat = _flatten(canonical)
    if not records:
        return _empty_object(flat), {}
    return _majority_node(records, flat)


# ---------------------------------------------------------------------------
# Validation (used by the app before accepting an edited schema file)
# ---------------------------------------------------------------------------

def validate_canonical(canonical: dict) -> list[str]:
    """Return a list of human-readable problems with a candidate schema
    (empty list = schema is OK to use). Both adapters double as validators:
    if either fails to translate the schema, that is reported directly."""
    if not isinstance(canonical, dict):
        return ["The schema file must contain a single JSON object."]

    problems: list[str] = []
    if canonical.get("type") != "object":
        problems.append('The top-level "type" must be "object".')
    if not isinstance(canonical.get("properties"), dict):
        problems.append('The top-level "properties" is missing or not an object.')

    for adapter_name, adapter in (("Google Gemini", to_gemini_schema),):
        try:
            adapter(canonical)
        except SchemaError as exc:
            problems.append(f"Could not prepare this schema for {adapter_name}: {exc}")
        except Exception as exc:  # defensive: never let a bad schema crash the server
            problems.append(f"Unexpected error preparing this schema for {adapter_name}: {exc}")

    return problems

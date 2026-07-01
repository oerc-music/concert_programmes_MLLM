# Output Schema

[`oxford_schema.json`](oxford_schema.json) defines the structure every
annotation must follow. It is a plain [JSON Schema](https://json-schema.org/)
file -- you do not need to know Python or Pydantic to read or edit it.

It is **generated from, and structurally identical to**, the hierarchical
Pydantic model (`SCHEMA.py`) used in the DLfM 2026 paper's experiment
(concert-level `c_*` fields, work-level `w_*` fields, movement-level `m_*`
fields; see Table 2 and the schema-tree figure in the paper). Editing it here
changes:

1. what the model is asked to extract, and
2. the metadata fields shown in the app's results view (the form on the
   right is generated automatically from this file).

## How to read it

- `properties` lists the fields at each level. `concerts` is the top level;
  each concert has `works`; each work may have `w_movements` and
  `w_perf_list`.
- `title` is the short human label shown in the app; `description` is the
  longer explanation shown as a tooltip and is also part of what the model
  reads as guidance.
- `"anyOf": [{"type": "string"}, {"type": "null"}]` means "a string, or
  `null` if nothing is printed". This is how the schema expresses that a
  field is optional -- the model is told to use `null` rather than guess.
- `$defs` holds the reusable building blocks (`Work`, `Movement`,
  `Performer`) referenced via `"$ref"` from other places, so each shape is
  defined once.

## What you can safely change

- **Add a field**: add a new entry under the relevant `properties` block
  with a `title`, `description`, and `type` (or `anyOf` with `null` if it's
  optional). Then update [`../prompts/PROMPT.txt`](../prompts/PROMPT.txt) so
  the extraction rules and worked example mention it -- the schema alone
  only constrains the *shape* of the output, not what counts as correct.
- **Rename a field**: edit the key in `properties` (and any matching key
  inside `required`). Keep `c_*` / `w_*` / `m_*` prefixes if you want to stay
  compatible with the CSV/JSONL output format described in the main README.
- **Remove a field**: delete its entry from `properties` (and from
  `required` if present).
- **Tighten a field**: e.g. add `"enum": ["Solo", "Duet", "Recital"]` to
  restrict a string field to a fixed set of values.

## Validity

The app validates this file on load and tells you exactly what is wrong if
it isn't valid JSON, or uses a feature outside what Google Gemini supports
for schema-constrained output. If you break something, you can always
restore the original from version control.

## How the schema reaches the model

Internally, the app translates this file into Google's structured-output
schema format (an OpenAPI 3.0 subset with uppercase type names) before each
request. You never need to do this yourself — edit this file only, and the
model will return data in the expected structure (`src/schema_adapters.py`,
if you're curious how).

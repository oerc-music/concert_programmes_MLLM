# GUI Demo — MLLM-Assisted Metadata Extraction from Historical Concert Programmes

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![DLfM 2026](https://img.shields.io/badge/DLfM_2026-paper-informational?style=flat-square)](https://doi.org/10.1145/3815723.3815726)
[![ORA snapshot](https://img.shields.io/badge/ORA_snapshot-10.5287%2Fora--n6yg5jgqy-lightgrey?style=flat-square)](https://dx.doi.org/10.5287/ora-n6yg5jgqy)
[![Status: GUI Demo](https://img.shields.io/badge/Status-GUI%20Demo-blue?style=flat-square)](#disclaimer)

> **A GUI demo for DLfM 2026 — MLLM-assisted concert programme metadata extraction.**
> Not finalised, publishable research software.

---

> [!CAUTION]
> **Experimental research software — read before use.**
>
> This is an experimental demonstration tool prepared for the 13th International Conference on Digital Libraries for Musicology (DLfM 2026). It is not finalised or peer-reviewed; its annotations are unverified, AI-generated first-pass drafts and must not be treated as authoritative catalogue metadata.
>
> **Using the free tier costs nothing.** This demo runs on Google Gemini's free tier, which requires no payment method and cannot bill you. Use a free-tier API key and no charges can arise.
>
> **If you enable billing on your API key** (switching to a paid tier) you may incur costs. In that case, you alone are responsible for setting spending and rate limits. The author and the University of Oxford accept no liability for any charges or other losses arising from use of this software, which is provided "as is", without warranty of any kind. See [DISCLAIMER.md](DISCLAIMER.md) for the full terms.
>
> **Images leave your machine** when you run a live annotation — each programme image is transmitted to Google Gemini per their terms of service. See [Privacy and data handling](#privacy-and-data-handling) before processing third-party cultural heritage material. The offline demo mode makes no network requests at all.

---

## What this is

This tool provides a local web-based graphical interface for the MLLM-assisted concert programme metadata-extraction workflow described in:

> Eck, S. O. & Page, K. R. (2026). *Multimodal Large Language Model-Assisted Metadata Extraction from Historical Concert Programmes (1872–1928).* Proceedings of the 13th International Conference on Digital Libraries for Musicology (DLfM 2026), Thessaloniki. DOI [10.1145/3815723.3815726](https://doi.org/10.1145/3815723.3815726)

Historical concert programmes are valuable musicological sources, yet most archival holdings lack item-level metadata. This tool uses a multimodal LLM to extract structured metadata (date, venue, performers, works, movements) from scanned programme images as a first-pass record ready for expert verification. From the paper's abstract:

> *"We implement a lightweight workflow comprising low-cost image capture using everyday consumer hardware, minimal preprocessing, schema-constrained JSON output, and repeated sampling using a simple consensus strategy of extracted metadata fields. [...] We find that MLLM output quality depends strongly on model choice and on expert-controlled design decisions (including hierarchical JSON schema definition and prompt specification)."*

The annotation workflow is identical to the paper's. This demo runs it on **Google Gemini's free tier**, chosen because its daily limits are more generous for hands-on testing. The paper's quantitative results used OpenAI models; Gemini was not part of that assessment, and its output is not part of the paper's findings.

The demo adds a local web interface (FastAPI + plain HTML/CSS/JS, no build step), an offline mode that replays the paper's pre-computed GPT-5 annotations for the 100 bundled samples without any API calls, and an Original ⇄ Binarised image toggle in the results viewer.

---

## Getting Started

See **[GETTING_STARTED.md](GETTING_STARTED.md)** for installation, launch, and API-key instructions.

---

## Adapting the prompt and schema

The extraction rules and output structure matter more to annotation quality than model choice, as the paper demonstrates.

**Prompt:** open `prompts/PROMPT.txt` in any text editor. The numbered rules (1–7) control how the model handles edge cases such as multiple concerts per image, absent fields, and date/time normalisation. You can also edit it live on the Setup screen.

**Schema:** open `schema/oxford_schema.json`. This [JSON Schema](https://json-schema.org/) (draft 2020-12) defines the field hierarchy (`concerts → works → movements / performers`). The app reads it at startup, sends it to the model as a structured-output constraint, and uses the `title` and `description` properties to drive the metadata display in the results viewer. Changes take effect on restart or after clicking "Save schema" in the app; the app validates the file on load and reports problems clearly.

---

## Output files

Each run produces a timestamped folder under `output/`:

```
output/
  YYYYMMDD-HHMMSS/
    IMG_7803.json          ← per-image nested annotation
    ...
    annotations.jsonl      ← all images, one JSON object per line
    annotations.csv        ← tidy long format (image, concert, work, field, value)
    run_metadata.json      ← provider, model, timestamp, prompt/schema hashes
```

The CSV format mirrors the paper's archived dataset.

---

## Privacy and data handling

- **API keys** are held in server memory only for the current session. They are never written to disk by this app and never committed to this repository.
- **Images are transmitted to Google Gemini** when you run a live annotation. Review Google's data-use and retention policy before processing third-party or sensitive material: [ai.google.dev/gemini-api/terms](https://ai.google.dev/gemini-api/terms)
- The **offline demo mode** makes no network requests. No data leaves your machine.
- The **100 bundled sample images** are historical concert programmes from the Bodleian Libraries (© Bodleian Libraries, University of Oxford). See [NOTICE_DATA.md](NOTICE_DATA.md) for data rights information.

---

## Attribution

### Sample images

The 100 concert programme images bundled in `input/` are reproduced from the *Gough Adds.* collection held by the **Bodleian Libraries, University of Oxford.** © Bodleian Libraries, University of Oxford. The [MIT License](LICENSE) covers only the code in this repository; the images are not covered by it. See [NOTICE_DATA.md](NOTICE_DATA.md) for the full rights statement and source catalogue references.

### Underlying research

This demo adapts the research pipeline reported in Eck & Page (2026). For the peer-reviewed methodology, results, and full experimental dataset, refer to the paper and the archived data snapshot — not to this demo.

Archived data snapshot (source data, MLLM outputs, ground truth): [dx.doi.org/10.5287/ora-n6yg5jgqy](https://dx.doi.org/10.5287/ora-n6yg5jgqy)

---

## Citation

If you use this demo in your work, please cite it as:

> Eck, S. O. (2026). *A GUI Demo for MLLM-Assisted Metadata Extraction from Historical Concert Programmes* [software]. University of Oxford. MIT License.

A machine-readable citation is available in [CITATION.cff](CITATION.cff).

To cite the underlying research (methodology, findings, ground truth):

> Sebastian Oliver Eck and Kevin R. Page. 2026. Multimodal Large Language Model-Assisted Metadata Extraction from Historical Concert Programmes (1872–1928). In 13th Annual Conference on Digital Libraries for Musicology (DLfM 2026), July 02, 2026, Thessaloniki, Greece. ACM, New York, NY, USA, 10 pages. https://doi.org/10.1145/3815723.3815726

---

## Provenance

| Artefact | Location |
|---|---|
| **This demo** | [github.com/oerc-music/concert\_programmes\_MLLM](https://github.com/oerc-music/concert_programmes_MLLM) |
| Archived data snapshot (source data, MLLM outputs, ground truth) | [dx.doi.org/10.5287/ora-n6yg5jgqy](https://dx.doi.org/10.5287/ora-n6yg5jgqy) |
| DLfM 2026 paper | [doi.org/10.1145/3815723.3815726](https://doi.org/10.1145/3815723.3815726) |

---

## AI declaration

This demo's GUI, FastAPI backend, and supporting scripts were built with substantial assistance from **Claude Code** (Anthropic; `claude-opus-4-8`), under the direction of the repository author. See [AI_DECLARATION.md](AI_DECLARATION.md) for the full declaration, including the DLfM 2026 policy on generative AI.

---

## Disclaimer

This software is experimental and provided "as is", without warranty of any kind, express or implied. The annotation workflow runs on the **Google Gemini free tier**, which requires no payment method; used this way, it cannot incur charges. If you enable billing on your API key, you may incur costs — you alone are responsible for setting spending and rate limits. The author and the University of Oxford accept no liability for any charges, data loss, or other losses arising from use of this software.

See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer and [SECURITY.md](SECURITY.md) for the API-key and data-handling security policy.

---

## License

The code in this repository is released under the [MIT License](LICENSE) © 2026 Sebastian Oliver Eck. The sample images in `input/` are not covered by this license — see [NOTICE_DATA.md](NOTICE_DATA.md).

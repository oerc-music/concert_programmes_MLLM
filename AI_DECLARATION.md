# AI Declaration

In alignment with the guidelines on the use of generative AI (GenAI) set out
by the 13th International Conference on Digital Libraries for Musicology
(DLfM 2026), we declare the use of GenAI in preparing this repository.

This repository is an **experimental GUI demo**, adapted from the research
codebase archived alongside the DLfM 2026 paper (see [README.md](README.md)
for the full provenance chain). Its preparation involved GenAI assistance at
two distinct levels:

## 1. Adaptation of the research pipeline

The metadata-extraction logic (prompt structure, JSON schema, and the
high-level extraction workflow) is **adapted, not copied**, from the
archived research codebase, whose own AI declaration is reproduced in the
ORA data snapshot (DOI [10.5287/ora-n6yg5jgqy](https://dx.doi.org/10.5287/ora-n6yg5jgqy)).
For this demo, the original first author (with AI-assisted coding support, see
below) re-engineered it from an asynchronous OpenAI Batch API pipeline into
a synchronous, interactive pipeline using the Google Gemini API, suitable
for live, single-image-at-a-time use in a GUI. The extraction
*rules*, the schema's field design, and the worked examples in the prompt
originate from the trained musicologist's design work reported in the paper
and are unchanged in substance.

## 2. Construction of the demonstration GUI

The web interface, FastAPI backend, provider adapters, and supporting
scripts in [`src/`](src/) were built with substantial assistance from
**Claude Code** (Anthropic; model `claude-opus-4-8`), under the direction
and review of the repository author. This includes:

- the FastAPI server and REST endpoints (`src/server.py`, `src/annotate.py`),
- the Google Gemini provider adapter and the JSON-Schema translation layer
  (`src/providers/`, `src/schema_adapters.py`),
- the offline/mock demo mode (`src/mock.py`),
- the entire frontend (`src/web/index.html`, `src/web/styles.css`,
  `src/web/app.js`), and
- this documentation set (README, declarations, in-folder guides).

All AI-assisted code and documentation has been reviewed and tested by the
author before inclusion. As with the original pipeline, this disclosure
follows the principle that **the use of generative AI tools does not change
authorial responsibility for the resulting work** (see the DLfM 2026 policy
reproduced below).

Notwithstanding the above, the author and the University of Oxford accept
**no liability** for errors, inaccuracies, costs incurred, damages, or other issues
arising from AI-assisted content in this repository or from the use or execution
of any scripts, code, or other materials it contains. This software is provided
"as is", without warranty of any kind. See [DISCLAIMER.md](DISCLAIMER.md) for the
full terms.

## 3. Scope limitation

This demo's annotation functionality has not itself been re-assessed against
the paper's ground truth in the way the original 11-model comparison was;
its purpose is to let users *try the workflow*, not to reproduce or extend
the paper's quantitative findings. The annotation workflow is identical to the paper's; this demo runs it on
Google Gemini's free tier, chosen because its daily limits are more
generous for hands-on testing. Gemini was never evaluated in the paper
itself — it is included here to lower the barrier to entry (no paid
account needed), consistent with the paper's own suggestion to test
"providers beyond OpenAI (e.g., Anthropic, Google)."

---

### DLfM 2026 Policy on the Use of Generative AI in Submissions

> We recognize that authors of academic works use a variety of tools in the research on which they report, and to prepare the report itself, ranging from simple to very sophisticated. Community opinion on the appropriateness of such tools may be varied and evolving; AI powered language tools have in particular led to significant debate. We note that tools may generate useful and helpful results, but also errors or misleading results; therefore, knowing which tools were used, and how, is relevant to evaluating and interpreting academic works.
>
> In the view of this, we:
>
> - require authors to report in their work any significant use of sophisticated tools, such as instruments and software; we now include in particular text-to-text generative AI among those tools that should be reported consistent with subject standards for methodology;
> - remind all colleagues that by signing their name as an author of a contribution, they each individually take full responsibility for all its contents, irrespective of how the contents were generated. If generative AI language tools generate inappropriate language, plagiarized content, errors, mistakes, incorrect references, or misleading content, and that output is included in academic works, it is the responsibility of the author(s);
> - stipulate that generative AI language tools should not be listed as an author; instead authors should refer to the first point;
> - run AI detection tools on all submissions in order to ensure accurate labour attribution.
>
> This statement mirrors the Music Encoding Conference 2026's policy itself adapted from the arXiv policy for authors' use of generative AI language tools. We reserve the right to amend this statement as discussions continue and evolve.
>
> DLfM reserves the right to implement sanctions on authors should generative AI be misused or found to be in breach of research ethics, up to and including a ban on future submissions.

# Extraction Prompt

[`PROMPT.txt`](PROMPT.txt) is the plain-text instruction sent to the model
alongside each image. It is **not** Python code -- it is the place a
musicologist or cataloguer (with or without a programmer's help) encodes
domain knowledge: how to read this particular collection's layout, what
counts as a "work" versus a "movement," how to normalise dates, and so on.

This file is also editable from inside the app (Setup screen → "Edit
prompt"), so you do not have to leave the browser to adjust it -- but
editing it here in a text editor works just as well, and is easier for
larger changes.

## Structure

The prompt has four parts, in order:

1. **SYSTEM / USER framing** -- sets the model's general behaviour (return
   one JSON object, no extra commentary).
2. **Extraction rules** (numbered 1–7) -- the collection-specific judgement
   calls: how to handle missing data, how to keep concert/work/movement
   levels separate, date/time normalisation, where performers and composers
   belong, and how to split works from movements.
3. **A quick-reference schema tree** -- a human-readable summary of the
   structure defined formally in
   [`../schema/oxford_schema.json`](../schema/oxford_schema.json). If you
   change the schema, update this tree to match (the app does not check
   that these two stay in sync).
4. **A worked example** -- a complete, correctly-filled-in JSON example.
   Models follow worked examples closely, so this is often the *most*
   effective place to fix a recurring mistake: add or amend an example that
   demonstrates the behaviour you want.

## Adapting this prompt to a different collection

The rules above were written for three Oxford student-society programmes
(1872–1928); a different collection -- different period, different
typographic conventions, a different language -- will need its own rules.
Concretely, you will likely want to:

- **Add or change a rule** when you notice a systematic mistake (e.g. the
  model is putting handwritten corrections in the wrong place, or splitting
  works incorrectly for your layout). The paper's "Error Sources and
  Practical Recommendations" section discusses several real examples of
  this from the original experiment.
- **Add a worked example** that shows an edge case specific to your
  collection (e.g. multi-language programmes, programmes with intervals
  listed, or a different way of crediting an orchestra).
- **Keep the schema and the rules in sync.** If you add a field to
  `oxford_schema.json`, add a rule (or extend the worked example) here that
  tells the model what should go in it -- an unconstrained schema field
  with no guidance tends to be filled inconsistently.

## A note on what this prompt cannot fix

Per the paper's findings, prompt changes mostly affect *judgement calls*
(what to call a field, how to split entries). They will not reliably fix
poor image legibility, and they cannot make the model attend to handwritten
annotations it has been told to deprioritise unless you say so explicitly
(see rule 1 and the paper's discussion of prompt underspecification around
handwritten corrections).

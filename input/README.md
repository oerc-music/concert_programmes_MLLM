# Input Images

This is the **default folder the app looks at**. Drop your own concert
programme images here (`.jpg`, `.jpeg`, or `.png`) and press Run -- or just
try the 100 bundled samples first.

## What's bundled

100 sample concert programmes (1872–1928) from three Oxford student music
societies held at the Bodleian Libraries, used as the test corpus in the
DLfM 2026 paper. **© Bodleian Libraries, University of Oxford** -- see
[`../NOTICE_DATA.md`](../NOTICE_DATA.md) for full rights information and
catalogue citations before reusing these images for anything beyond trying
this demo.

- The images directly in this folder are **downscaled colour scans**
  (long edge 1600px, JPEG) -- legible, and small enough to keep the repo
  lightweight. This is what gets sent to the model by default.
- [`binarised/`](binarised/) holds the matching **pre-processed, binarised**
  versions (adaptive thresholding, exactly as used in the paper's
  experiment) for the same 100 images. The app's results view lets you
  toggle between the two; you can also choose to send the binarised version
  to the model instead of colour (Setup screen → image processing setting).

Full-resolution originals (2-3 MB each) are **not** included here to keep
this repository lightweight; they are available in the archived experimental
snapshot referenced in the main README.

## Using your own images

Just copy your own scans or photos into this folder (any subfolder
structure is fine -- the app scans recursively). A few practical notes
carried over from the paper's own image-capture process:

- Reasonably flat, well-lit, one-sided scans or photos work best.
- Very large files are fine -- the app downscales before sending anything to
  a model.
- If your collection has visually different layout conventions than the
  bundled Oxford samples, you will likely want to adapt
  [`../prompts/PROMPT.txt`](../prompts/PROMPT.txt) (and possibly
  [`../schema/oxford_schema.json`](../schema/oxford_schema.json)) before
  running a large batch -- see those folders' own READMEs.

## Choosing a different folder

The Setup screen lets you point the app at any other folder on your machine
instead of this one, if you'd rather keep your own images elsewhere.

# Getting Started

← [README.md](README.md)

---

## Requirements

**Python 3.10 or later** is required. Check your version:

```bash
python --version
```

If you need to install Python:
- **Windows / macOS:** download from [python.org/downloads](https://www.python.org/downloads/) and run the installer. On Windows, tick **"Add Python to PATH"** during setup.
- **macOS (Homebrew):** `brew install python@3.12`
- **Linux:** `sudo apt install python3.12 python3.12-venv` (Ubuntu/Debian) or your distro's equivalent.

---

## Install and launch

**1. Create a virtual environment:**

```bash
python -m venv .venv
```

**2. Activate it:**

Windows:

```
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

**3. Install dependencies:**

```bash
pip install -r requirements.txt
```

**4. Launch:**

```bash
python src/run_demo.py
```

The app opens at [http://127.0.0.1:8000](http://127.0.0.1:8000). Press `Ctrl+C` in the terminal to stop it.

---

## Quick start: offline mode (no API key needed)

1. Launch the app (steps above).
2. On the **Setup** screen, enable the **Offline demo mode** toggle.
3. Optionally click a few thumbnails in the gallery to select specific images, or leave none selected to annotate the first N.
4. Click **Run annotation.** The app replays pre-computed GPT-5 annotations for the bundled samples — no network, no quota, no cost.
5. Explore the **Results** screen: browse images, toggle between Original and Binarised views, and download the CSV.

---

## Live annotation (requires a free API key)

### Get a free Gemini API key

> [!NOTE]
> Google Gemini offers a free tier through Google AI Studio. No billing account is required. Free-tier rate limits apply (roughly 15 requests/minute and a per-day cap). For current limits, see [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits).

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with a Google account.
2. Accept the Terms of Service if prompted (a default project is created automatically).
3. Click **"Create API key"** and copy it. *(Shown in full only once.)*

### Use the key in the app

**Option A — paste each session:** paste your key into the **API key** field on the Setup screen. It stays in memory only and is never written to disk.

**Option B — save it to a `.env` file** (persists across sessions):

```bash
cp .env.example .env
```

Open `.env` and paste your key next to `GEMINI_API_KEY=`. The app reads it on launch. The `.env` file is gitignored and never committed.

### Run an annotation

1. Launch the app and paste your API key (or use `.env`).
2. Choose a model from the dropdown.
3. **Select images:** click thumbnails in the gallery — a checkmark appears on selected images. Click again to deselect. Leave nothing selected to annotate the first N images (set N in the "Images to annotate" field).
4. Click **Run annotation.**
5. Watch the progress screen, then explore results. Output is saved automatically to `output/<YYYYMMDD-HHMMSS>/`.

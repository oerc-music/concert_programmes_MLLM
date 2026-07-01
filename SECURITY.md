# Security Policy

## Scope

This repository contains an **experimental demonstration tool** — a local web application intended to be run on a personal machine by a single user. It is not a production service, not deployed on public servers, and not intended for multi-user or networked use. Security guarantees are limited accordingly.

## API key handling

API keys entered in the app's Setup screen are:

- **Held in server memory only** for the duration of the session.
- **Never written to disk** by this application.
- **Never committed to this repository** — the repo ships only `.env.example` (a template with no real keys).
- Discarded when the server process stops.

Keys may alternatively be placed in a local `.env` file (copied from `.env.example`). This file is listed in `.gitignore` and is never committed.

## No secrets in the repository

This repository does not contain, and must never contain:

- API keys or credentials of any kind.
- The `.env` file (only `.env.example`).
- Full-resolution source images (only downscaled samples are included).

If you believe a secret has been accidentally committed, please report it immediately (see below) so it can be rotated and the commit history cleaned.

## Network requests

A live annotation run transmits programme images to **Google Gemini** per [Google's terms of service](https://ai.google.dev/gemini-api/terms). No other outbound network requests are made by this application. The **offline demo mode** makes no network requests at all.

## Supported versions

This is a frozen experimental demo released alongside the DLfM 2026 paper. It is not actively maintained. No security patches will be issued for post-publication vulnerabilities; users should treat it as research software run at their own risk.

## Reporting a vulnerability

If you discover a security issue in this repository (e.g. a committed secret, an injection vulnerability in the local web app, or a supply-chain concern in a listed dependency), please report it by:

1. Opening a **GitHub Issue** with the label `security` (for non-sensitive issues), or
2. Emailing the repository author directly at the address listed in [CITATION.cff](CITATION.cff) (for sensitive disclosures, e.g. committed credentials).

Please do not open a public issue for matters involving exposed credentials — contact the author privately first so the key can be rotated before public disclosure.

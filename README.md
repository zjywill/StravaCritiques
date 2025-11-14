# Strava Activity Critique Toolkit

This repository bundles a LangChain-powered CLI, Strava automation utilities, and a Flask OAuth demo that work together to download your latest rides, ask an LLM for tongue-in-cheek critiques (in Chinese), and sync those critiques back to Strava.

## Features

- LangChain CLI (`main.py`) that reads Strava activities and generates sarcastic workout critiques via `ChatOpenAI`.
- Selenium-based OAuth helper (`stravalogin.py`) to capture Strava tokens without leaving the terminal.
- Data helpers (`latest_activity.py`, `comment_activity.py`) for pulling activities and updating Strava descriptions.
- Flask sample app (`strava/app.py`) illustrating the full OAuth flow locally.

## Repository layout

- `main.py` – entry point that wires LangChain prompts + LLM and produces `activity_critiques.json`.
- `latest_activity.py` – fetches recent activities using stored OAuth tokens.
- `comment_activity.py` – uploads saved critiques to Strava activity descriptions.
- `stravalogin.py` – Selenium automation for creating/refreshing tokens under `user_token/`.
- `strava/` – Flask OAuth demo (`create_app`) plus docs in `strava/README.md`.

## Prerequisites

- Python 3.9+ (tested on CPython; create a virtualenv).
- Chrome browser (for Selenium automation) and a Strava application configured at <https://www.strava.com/settings/api>.
- An LLM key compatible with `langchain-openai`. The scripts look for `ONE_API_KEY` (preferred) but older `.env` files may still use `OPENAI_API_KEY`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                   # populate secrets before running networked scripts
```

Always load `.env` (via `source .venv/bin/activate && export $(cat .env)`) or rely on `python-dotenv` before invoking CLI tools that talk to Strava/OpenAI.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `ONE_API_KEY` / `OPENAI_API_KEY` | API key for the configured LLM backend. |
| `ONE_API_MODEL` | Optional override of the chat model (default `gpt-3.5-turbo`). |
| `ONE_API_REMOTE` | Optional custom base URL for compatible OpenAI-style endpoints. |
| `LLM_SYSTEM_PROMPT` | Customize the critique instructions without editing code. |
| `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` | Credentials from your Strava app. |
| `STRAVA_REDIRECT_URI` | Must match the redirect registered in Strava (default `http://localhost:5000/callback`). |
| `FLASK_SECRET_KEY` | Session secret for the Flask OAuth demo. |

Keep all secrets in `.env` and never commit the generated `user_token/` files or `.env` itself.

## Workflow

### 1. Capture Strava tokens (one-time or when scopes change)

Run the automation against the local Flask server (see below) to save a token JSON:

```bash
python stravalogin.py --headless
```

The script opens `http://127.0.0.1:5000/login`, waits for you to authorize, then writes `user_token/strava_token_*.json`. Use `--scope` to request precise Strava scopes or `--user-data-dir`/`--profile-directory` to reuse existing Chrome sessions.

### 2. Fetch the latest activities

```bash
python latest_activity.py --per-page 5
```

This loads the newest token under `user_token/`, refreshes it when near expiry, and saves the fetched workouts to `latest_activities.json`. Use `--token-file` to target a specific JSON or `--output` to change the destination file.

### 3. Generate sarcastic critiques with LangChain

```bash
python main.py
```

`main.py` loads `.env`, builds a `ChatPromptTemplate` + `ChatOpenAI` chain, and processes each activity in `latest_activities.json`. The output (critique text plus upload metadata) is persisted to `activity_critiques.json`. Adjust tone by exporting `LLM_SYSTEM_PROMPT` or swap the backend by editing `build_chain`.

### 4. Push critiques back to Strava

```bash
python comment_activity.py --max-count 3
```

The uploader reads `activity_critiques.json`, skips entries already marked `uploaded=true`, and updates the Strava activity `description` via the API. Use `--dry-run` to preview the payload, `--token-file` to pick a credential, and `--critiques-file` for custom JSON paths.

## Flask OAuth demo

The `strava/` package exposes `create_app` and serves the login/demo UI:

```bash
source .venv/bin/activate
flask --app strava.app --debug run
```

After exporting the Strava credentials listed above, open <http://localhost:5000/login>. Successful consent stores the athlete profile + tokens in the Flask session and renders the JSON at `/profile`. See `strava/README.md` for endpoint details and customization tips.

## Testing & linting

Add tests under `tests/` following the module layout (e.g., `tests/test_main.py`) and run them via:

```bash
pytest
```

Use `ruff --fix .` or `black .` before committing if you add formatting tooling, and mock outbound HTTP (Strava or LLM) in unit tests to avoid leaking secrets.

## Data hygiene

- `.env`, `user_token/`, and `latest_activities.json` contain sensitive data—keep them local.
- Never log athlete tokens or personal metrics outside of trusted debugging.
- When sharing repro steps, sanitize `activity_critiques.json` and Strava payloads.

With these scripts you can iterate on creative Strava commentary quickly, while the Flask app and automation utilities handle all of the OAuth heavy lifting.

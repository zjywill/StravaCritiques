# Repository Guidelines

## Project Structure & Module Organization
- Root Python entry point lives in `main.py`; it wires LangChain prompts and `ChatOpenAI` for the CLI demo.  
- `latest_activity.py` and `stravalogin.py` hold Strava-related utilities (automation, data fetchers). Keep any new scripts at the root or group them in `tools/` if they grow.  
- Flask OAuth demo code resides in `strava/` with `app.py` exposing `create_app`; accompanying docs live in `strava/README.md`.  
- Configuration secrets belong in `.env`; never commit tokens stored in `user_token` or similar artifacts.

## Build, Test, and Development Commands
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt              # sync poetry-free dependencies
python main.py "示例问题"                      # run the LangChain CLI (prompts if no arg)
flask --app strava.app --debug run           # serve the Strava OAuth demo on :5000
python stravalogin.py --headless             # automate the OAuth flow against the local server
```
Always load `.env` (see `.env.example`) before running networked commands.

## Coding Style & Naming Conventions
- Follow Black/PEP 8 layout: 4-space indents, import grouping (stdlib, third-party, local), and expressive function names (`build_chain`, `create_app`).  
- Use type hints and docstrings for public helpers; prefer `from __future__ import annotations` for forward references as in existing modules.  
- Constants stay upper snake case (`AUTHORIZE_URL`), environment keys uppercase, and CLI/script names remain short snake case.  
- Run `ruff --fix .` or `black .` locally if you introduce formatting tooling; include config in the repo when adopted.

## Testing Guidelines
- Adopt `pytest` for new coverage; mirror the module layout under `tests/` (e.g., `tests/test_main.py`, `tests/strava/test_app.py`).  
- Name tests after behavior (`test_build_chain_uses_prompt`).  
- For networked flows, mock Strava responses via `responses` or `requests-mock`.  
- Target at least smoke coverage for new endpoints and any CLI behavior; document any manual-only verification steps in PRs.

## Commit & Pull Request Guidelines
- Commits follow short imperative subjects (`Add Strava callback guard`); keep <=72 chars and explain “what/why” in the body if needed.  
- PRs should describe the change, list test evidence (`pytest`, manual OAuth run), and link issues. Include screenshots or curl output when UI/HTTP responses change.  
- Note secrets handling in PRs (e.g., confirm `.env` changes stay local) and mention rollout steps if OAuth scopes or environment variables shift.

## Security & Configuration Tips
- Never log access tokens or athlete data outside local debugging; scrub debug prints before merging.  
- Regenerate `.env` entries when rotating Strava or OpenAI credentials and update README snippets if defaults change.  
- When sharing repro data, sanitize `latest_activities.json` and any session dumps before attaching them to issues.

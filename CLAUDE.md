# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
# Set up virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy environment template and configure secrets
cp .env.example .env  # Edit .env with your API keys
```

### Common Development Tasks
```bash
# Run the main LangChain CLI to generate activity critiques
python ai_gen_comment.py

# Fetch latest Strava activities
python latest_activity.py --per-page 5

# Upload critiques to Strava activities
python post_comment.py --max-count 3

# Start Flask OAuth demo server
flask --app strava.app --debug run

# Automate OAuth token capture using Selenium
python stravalogin.py --headless

# Run tests (when they exist)
pytest

# Code formatting (if tooling is added)
ruff --fix .
black .
```

### Environment Variables Required
Essential secrets that must be configured in `.env` before running networked commands:
- `ONE_API_KEY` or `OPENAI_API_KEY` - LLM API key
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` - Strava app credentials
- `FLASK_SECRET_KEY` - Flask session secret
- `ONE_API_MODEL` - Optional LLM model override (default: gpt-3.5-turbo)
- `ONE_API_REMOTE` - Optional custom OpenAI endpoint
- `LLM_SYSTEM_PROMPT` - Optional custom critique instructions

## Architecture

This is a Strava activity critique toolkit that combines LangChain LLM processing with Strava API integration. The system follows a batch processing workflow:

### Core Components

**ai_gen_comment.py**: LangChain CLI entry point that orchestrates the critique generation pipeline
- Loads Strava activities from `latest_activities.json`
- Builds LangChain prompt templates with ChatOpenAI
- Generates Chinese-language sarcastic critiques in `build_activity_prompt()`
- Persists results to `activity_critiques.json` with upload tracking

**latest_activity.py**: Strava API data fetcher
- Handles OAuth token management with automatic refresh
- Fetches activities from Strava API v3 endpoints
- Supports token file selection and pagination

**post_comment.py**: Strava API writer
- Uploads generated critiques as activity descriptions
- Tracks upload status to prevent duplicates
- Provides dry-run mode for safe testing

**stravalogin.py**: Selenium-based OAuth automation
- Automates browser token capture against local Flask server
- Manages Chrome profiles and session persistence
- Supports headless operation and custom timeouts

**strava/app.py**: Flask OAuth demo application
- Implements full Strava OAuth flow locally
- Provides `/login`, `/callback`, and `/profile` endpoints
- Manages Flask sessions and token exchange

### Data Flow
1. **Token Capture**: `stravalogin.py` → `user_token/*.json`
2. **Activity Fetch**: `latest_activity.py` → `latest_activities.json`
3. **Critique Generation**: `ai_gen_comment.py` → `activity_critiques.json`
4. **Upload**: `post_comment.py` → Strava API descriptions

### Key Patterns
- **OAuth Token Management**: Centralized token refresh logic in `latest_activity.py` shared across scripts
- **Error Handling**: Comprehensive rate limiting and API error handling for Strava endpoints
- **Configuration**: All secrets externalized to `.env` with python-dotenv loading
- **CLI Design**: ArgumentParser-based interfaces with `--help` documentation and sensible defaults

## Important Notes

- Chrome browser required for Selenium automation in `stravalogin.py`
- Always load `.env` before running networked commands (scripts use python-dotenv)
- Generated files (`user_token/*.json`, `latest_activities.json`, `activity_critiques.json`) contain sensitive data - keep local
- The system generates critiques in Chinese by default; customize via `LLM_SYSTEM_PROMPT` environment variable
- Strava OAuth scopes required: `activity:read` for fetching, `activity:write` for uploading descriptions

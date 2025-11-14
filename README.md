# LangChain Python Demo

This repository contains a minimal Python command-line app wired up to
[LangChain](https://python.langchain.com) so you can quickly experiment with
LLM-powered prompts.

## Prerequisites

- Python 3.9+ (newer versions should also work)
- An OpenAI API key stored in an `.env` file (see below)

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Fill in your key
python main.py "帮我写一首俳句"
```

If you omit the question argument the app will prompt for interactive input.

## Configuration

The app expects `OPENAI_API_KEY` to be present in the environment (loaded
via `python-dotenv`). You can add more environment variables to `.env`
as needed.

## How it works

`main.py` assembles a simple LangChain runnable consisting of:

1. A chat prompt template (system + human messages)
2. `ChatOpenAI` as the LLM
3. A string output parser to convert the response to plain text

You can customize the system prompt or swap the LLM for a different provider
simply by editing `build_chain` in `main.py`.

## Strava OAuth demo

Inside the `strava/` directory you'll find a minimal Flask application that
performs the Strava OAuth login flow:

```bash
source .venv/bin/activate
flask --app strava.app --debug run
```

Before running it, set `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`,
`STRAVA_REDIRECT_URI`, and `FLASK_SECRET_KEY` inside `.env` (see
`.env.example`). Then open <http://localhost:5000/login> and finish the
authorization flow. The returned athlete profile and tokens are stored in the
session and shown at `/profile`. See `strava/README.md` for more detail.

To automatically launch a browser, finish the OAuth flow, and collect the tokens
exposed at `/profile`, run `python stravalogin.py`. The script relies on
Selenium 4.20+ which downloads/locates the matching ChromeDriver automatically.
Chrome must be installed locally, and the local Flask app must already be
running on `http://127.0.0.1:5000`. You can add `--headless` to run without
opening a visible browser window. Pass `--user-data-dir=/path/to/Chrome/User Data`
(and optionally `--profile-directory="Profile 1"`) if you want the automation to
reuse the cookies and sessions from an existing Chrome profile.

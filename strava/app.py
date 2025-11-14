from __future__ import annotations

import os
from typing import Dict, Any

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, request, session, url_for, jsonify
from urllib.parse import urlencode

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    app.config["STRAVA_CLIENT_ID"] = os.getenv("STRAVA_CLIENT_ID")
    app.config["STRAVA_CLIENT_SECRET"] = os.getenv("STRAVA_CLIENT_SECRET")
    app.config["STRAVA_REDIRECT_URI"] = os.getenv("STRAVA_REDIRECT_URI", "http://localhost:5000/callback")

    required = ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET"]
    missing = [key for key in required if not app.config.get(key)]
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(f"Missing Strava config values: {missing_str}. Update your .env file.")

    @app.route("/")
    def index() -> Any:
        if "athlete" in session:
            athlete = session["athlete"]
            return {
                "logged_in": True,
                "athlete": {
                    "id": athlete.get("id"),
                    "username": athlete.get("username"),
                    "firstname": athlete.get("firstname"),
                    "lastname": athlete.get("lastname"),
                },
            }
        return {
            "logged_in": False,
            "login_url": url_for("login", _external=True),
        }

    @app.route("/login")
    def login() -> Any:
        params = {
            "client_id": app.config["STRAVA_CLIENT_ID"],
            "redirect_uri": app.config["STRAVA_REDIRECT_URI"],
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": request.args.get("scope", "read"),
        }
        return redirect(f"{AUTHORIZE_URL}?{urlencode(params)}")

    @app.route("/callback")
    def callback() -> Any:
        error = request.args.get("error")
        if error:
            return {"error": error}, 400

        code = request.args.get("code")
        if not code:
            return {"error": "Missing authorization code."}, 400

        token_payload = _exchange_code_for_token(app, code)
        session["access_token"] = token_payload.get("access_token")
        session["refresh_token"] = token_payload.get("refresh_token")
        session["expires_at"] = token_payload.get("expires_at")
        session["athlete"] = token_payload.get("athlete", {})

        return redirect(url_for("profile"))

    @app.route("/profile")
    def profile() -> Any:
        athlete = session.get("athlete")
        if not athlete:
            return redirect(url_for("login"))
        return jsonify(
            {
                "athlete": athlete,
                "access_token": session.get("access_token"),
                "refresh_token": session.get("refresh_token"),
                "expires_at": session.get("expires_at"),
            }
        )

    @app.route("/logout")
    def logout() -> Any:
        session.clear()
        return {"message": "Logged out"}

    return app


def _exchange_code_for_token(app: Flask, code: str) -> Dict[str, Any]:
    data = {
        "client_id": app.config["STRAVA_CLIENT_ID"],
        "client_secret": app.config["STRAVA_CLIENT_SECRET"],
        "code": code,
        "grant_type": "authorization_code",
    }
    response = requests.post(TOKEN_URL, data=data, timeout=10)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    create_app().run(debug=True)

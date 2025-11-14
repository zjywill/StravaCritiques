# Strava OAuth Demo

This lightweight Flask app demonstrates how to perform the Strava OAuth login
flow and capture the authenticated athlete profile in the session.

## Configure Strava

1. Visit <https://www.strava.com/settings/api> and create an application.
2. Set the authorization callback domain to `localhost` and callback path to
   `/callback` (or whatever you configure in `.env`).
3. Copy the **Client ID** and **Client Secret** into your `.env` file:

```
STRAVA_CLIENT_ID=12345
STRAVA_CLIENT_SECRET=mysupersecret
STRAVA_REDIRECT_URI=http://localhost:5000/callback
FLASK_SECRET_KEY=dev-secret
```

## Run the demo

```bash
source .venv/bin/activate
flask --app strava.app --debug run
```

Then open <http://localhost:5000/login>. After approving the app in Strava
you'll be redirected back to `/profile` which shows the athlete details
stored in the session. Use `/logout` to clear the session.

The module is self-contained, so you can import `create_app` and mount it
inside an existing Flask/WSGI project if desired.

# Raghav Portfolio and Flask Chatbot

## Project structure

- `app.py` — Flask app, PDF profile loading, Groq chat API, and Gmail SMTP handlers.
- `templates/index.html` — portfolio page, floating chatbot, and contact form.
- `Profile.pdf` — profile knowledge source for chat and the PDF attachment sent by email.
- `requirements.txt` — Python dependencies.
- `.env` — local configuration; keep this file private and out of version control.

## Features and endpoints

- `GET /` serves the portfolio page.
- `POST /api/chat` answers questions about the profile using Groq and the text extracted from `Profile.pdf`.
- `POST /api/email` sends the visitor a copy of `Profile.pdf`.
- `POST /api/contact` forwards the visitor's name, reply address, subject, and message to `GMAIL_ADDRESS`.

## Configuration

Set these values in `.env`:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
GMAIL_ADDRESS=you@example.com
GMAIL_APP_PASSWORD=your_gmail_app_password
PROFILE_PDF=Profile.pdf
PORT=5000
```

`GMAIL_APP_PASSWORD` must be a Gmail App Password. The contact form and profile email feature share this SMTP configuration. Keep `.env` out of Git and rotate credentials if they have been exposed.

## Run locally

1. Install dependencies with `pip install -r requirements.txt`.
2. Add `Profile.pdf` beside `app.py` and create `.env` using the configuration above.
3. Run `python app.py` and open `http://localhost:5000` (or the port set in `.env`).

Serve the page through Flask; opening the HTML file directly will not provide its API endpoints.

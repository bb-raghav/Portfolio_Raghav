import os
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from groq import Groq
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
PROFILE_PDF = BASE_DIR / os.getenv("PROFILE_PDF", "Profile.pdf")


def load_profile_text():
    """Read the portfolio profile PDF used as the chatbot knowledge base."""
    if not PROFILE_PDF.exists():
        raise FileNotFoundError(
            f"Profile PDF not found: {PROFILE_PDF}"
        )

    reader = PdfReader(str(PROFILE_PDF))
    pages = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())

    return "\n\n".join(pages).strip()


try:
    PROFILE_TEXT = load_profile_text()
except Exception as exc:
    PROFILE_TEXT = ""
    print(f"[PROFILE] {exc}")


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing from .env")

    return Groq(api_key=api_key)


def build_system_prompt():
    return f"""
You are Raghav Bubna's AI assistant on his professional portfolio website.

Answer questions ONLY about Raghav's professional profile.

You may discuss:
- Career
- Professional background
- Skills
- Projects
- Certifications
- Work experience
- Internships
- Achievements
- Education
- Current training

Use ONLY the profile information supplied below.

Speak in the first person as Raghav when appropriate.

Be professional, accurate, concise, and natural.

Do not invent, assume, exaggerate, or hallucinate information.

If the requested information is not available in the profile, say exactly:
"I am not sure about that based on the available profile information."

Profile information:
{PROFILE_TEXT}
""".strip()


def build_email_prompt():
    return f"""
Prepare detailed professional information about Raghav Bubna for a visitor
who requested it by email.

Use ONLY the profile information below.

Cover relevant information about:
- Education
- Career background
- Technical skills
- Projects
- Work experience
- Internships
- Certifications
- Achievements
- Current training

Only include information supported by the profile.

Do not invent, assume, exaggerate, or add unsupported information.

Write polished plain-text email content. Do not include a subject line.

Profile information:
{PROFILE_TEXT}
""".strip()


def is_email_request(text):
    """Detect natural requests such as 'send me detail info over mail'."""
    prompt = text.lower().strip()

    email_terms = ["email", "e-mail", "mail"]
    send_terms = ["send", "mail", "email"]
    detail_terms = [
        "detail", "details", "detailed", "information", "info",
        "profile", "resume", "background", "experience",
        "skills", "projects", "career", "work"
    ]

    has_email = any(x in prompt for x in email_terms)
    has_send = any(x in prompt for x in send_terms)
    has_detail = any(x in prompt for x in detail_terms)

    return has_email and (has_send or has_detail)


def valid_email(email):
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return bool(re.fullmatch(pattern, email.strip()))


def send_email(recipient, attachment_path):
    """Send a short professional email with the profile PDF attached."""

    gmail_address = os.getenv("GMAIL_ADDRESS", "").strip()
    gmail_password = (
        os.getenv("GMAIL_APP_PASSWORD", "")
        .replace(" ", "")
        .strip()
    )

    if not gmail_address:
        return False, "GMAIL_ADDRESS is missing from .env"

    if not gmail_password:
        return False, "GMAIL_APP_PASSWORD is missing from .env"

    attachment_path = Path(attachment_path)

    if not attachment_path.exists():
        return False, "Profile PDF could not be found."

    message = EmailMessage()

    message["Subject"] = "Raghav Bubna - Profile"
    message["From"] = gmail_address
    message["To"] = recipient

    # Short, professional email body.
    message.set_content(
        """Hello,

Thank you for your interest in my profile.

Please find my profile attached for your reference.

Regards,
Raghav
"""
    )

    try:
        # Attach the actual Profile.pdf.
        with attachment_path.open("rb") as pdf_file:
            pdf_data = pdf_file.read()

        message.add_attachment(
            pdf_data,
            maintype="application",
            subtype="pdf",
            filename="Raghav_Bubna_Profile.pdf",
        )

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(gmail_address, gmail_password)
            smtp.send_message(message)

        return True, "Profile has been sent to your email."

    except smtplib.SMTPAuthenticationError:
        print("[SMTP] Authentication failed.")
        return False, "Gmail authentication failed."

    except smtplib.SMTPException as exc:
        print(f"[SMTP] {exc}")
        return False, "The email service returned an SMTP error."

    except Exception as exc:
        print(f"[EMAIL] {exc}")
        return False, "Unable to send the email right now."


def send_contact_email(name, sender_email, subject, body):
    """Forward a portfolio contact message to the configured Gmail inbox."""
    gmail_address = os.getenv("GMAIL_ADDRESS", "").strip()
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()

    if not gmail_address or not gmail_password:
        return False, "Email sending is not configured. Please use the direct email link."

    message = EmailMessage()
    message["Subject"] = f"Portfolio contact: {subject}"
    message["From"] = gmail_address
    message["To"] = gmail_address
    message["Reply-To"] = sender_email
    message.set_content(f"Name: {name}\nEmail: {sender_email}\n\n{body}")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(gmail_address, gmail_password)
            smtp.send_message(message)
        return True, "Your message has been sent. Thanks for reaching out."
    except smtplib.SMTPAuthenticationError:
        print("[SMTP] Contact form authentication failed.")
        return False, "Email authentication failed. Please use the direct email link."
    except (smtplib.SMTPException, OSError) as exc:
        print(f"[SMTP] Contact form send failed: {exc}")
        return False, "Unable to send your message right now. Please use the direct email link."


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get("message", "")).strip()
    history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    if not PROFILE_TEXT:
        return jsonify({
            "error": "Profile.pdf could not be loaded. Add it to the project root."
        }), 500

    # Email intent is handled by Flask before Groq.
    if is_email_request(user_message):
        return jsonify({
            "answer": (
                "Sure. Please enter your email address below, "
                "and I will send you the detailed information."
            ),
            "email_request": True
        })

    messages = [{"role": "system", "content": build_system_prompt()}]

    # Keep only safe, recent conversation messages.
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({
                "role": role,
                "content": content[:6000]
            })

    # Add current message unless already present.
    if not (
        messages[-1].get("role") == "user"
        and messages[-1].get("content") == user_message
    ):
        messages.append({"role": "user", "content": user_message})

    try:
        response = get_groq_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )

        answer = response.choices[0].message.content

        return jsonify({
            "answer": answer,
            "email_request": False
        })

    except Exception as exc:
        print(f"[GROQ] {exc}")
        return jsonify({
            "error": "Unable to generate a response right now."
        }), 500


@app.post("/api/email")
def email_profile():
    data = request.get_json(silent=True) or {}
    recipient = str(data.get("email", "")).strip()

    if not recipient:
        return jsonify({
            "error": "Please enter an email address."
        }), 400

    if not valid_email(recipient):
        return jsonify({
            "error": "Please enter a valid email address."
        }), 400

    if not PROFILE_PDF.exists():
        return jsonify({
            "error": "Profile.pdf could not be found."
        }), 500

    success, message = send_email(
        recipient=recipient,
        attachment_path=PROFILE_PDF,
    )

    if not success:
        return jsonify({
            "error": message
        }), 500

    return jsonify({
        "message": message
    })


@app.post("/api/contact")
def contact():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    sender_email = str(data.get("email", "")).strip()
    subject = str(data.get("subject", "")).strip()
    body = str(data.get("message", "")).strip()

    if not all((name, sender_email, subject, body)):
        return jsonify({"error": "Please complete all contact fields."}), 400
    if len(name) > 120 or len(subject) > 200 or len(body) > 5000:
        return jsonify({"error": "One or more fields are too long."}), 400
    if not valid_email(sender_email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if any(char in subject for char in "\r\n"):
        return jsonify({"error": "Subject must be a single line."}), 400

    success, message = send_contact_email(name, sender_email, subject, body)
    if not success:
        return jsonify({"error": message}), 500
    return jsonify({"message": message})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=True
    )

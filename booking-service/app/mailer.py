"""Sends reminder emails. If SMTP_HOST is not set, emails are only printed to the log."""
import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger("mailer")


def send_email(to: str, subject: str, body: str) -> str:
    """Returns 'sent', 'simulated' (no SMTP configured) or 'failed'."""
    host = os.getenv("SMTP_HOST")
    if not host:
        log.info("[simulated email] to=%s subject=%s", to, subject)
        return "simulated"
    msg = EmailMessage()
    msg["From"] = os.getenv("MAIL_FROM", "fest@college.local")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "1025")), timeout=10) as s:
            if os.getenv("SMTP_USER"):
                s.starttls()
                s.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
            s.send_message(msg)
        return "sent"
    except Exception as exc:
        log.warning("email to %s failed: %s", to, exc)
        return "failed"

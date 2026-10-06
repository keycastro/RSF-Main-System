from __future__ import annotations

from email.message import EmailMessage

from flask import current_app

from .gmail_ops import connected_email, gmail_connected, send_raw_message


def password_recovery_email_ready() -> bool:
    return gmail_connected()


def send_password_reset_code(*, to_email: str, full_name: str, code: str) -> None:
    if not gmail_connected():
        raise RuntimeError("RSF password recovery email is not connected yet.")

    sender = connected_email() or current_app.config.get("RSF_EMAIL_ADDRESS", "") or "me"
    message = EmailMessage()
    message["Subject"] = "RSF Workspace password reset code"
    message["From"] = sender
    message["To"] = to_email
    message.set_content(
        f"""Hi {full_name or 'RSF user'},

Your RSF Workspace password reset code is:

{code}

This code expires in 10 minutes and can be used only once.

If you did not request a password reset, you can ignore this email.

Realty Systems Foundry
"""
    )
    send_raw_message(message.as_bytes())

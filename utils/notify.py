"""Email and SMS notifications (OTP emails, booking confirmations, receipts).

``EMAIL_PROVIDER=console`` (default) logs every message to the server log, which
is what local development and the test-suite use. Set ``EMAIL_PROVIDER=smtp``
and the SMTP_* env vars to send real mail. Nothing here hard-codes credentials
and every send is best-effort: a failed notification never breaks a booking.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

PURPOSE_LABELS = {
    "signup": "verify your phone number",
    "login": "sign in to RentKart",
    "change_phone": "confirm your new phone number",
    "alternate_phone": "verify your alternate phone number",
    "reset_password": "reset your RentKart password",
}


def _cfg(key, default=""):
    env_val = os.environ.get(key)
    if env_val is not None and env_val != "":
        return env_val
    if has_app_context():
        val = current_app.config.get(key)
        if val is not None and val != "":
            return val
    return default


def send_email(to_email, subject, body) -> tuple:
    """Send (or log) an email. Returns ``(ok, message)``; never raises."""
    recipient = str(to_email or "").strip()
    if not recipient or "@" not in recipient:
        return False, "Missing recipient email"
    sender = str(_cfg("MAIL_FROM", "no-reply@rentkart.local"))
    provider = str(_cfg("EMAIL_PROVIDER", "console")).lower()

    if provider != "smtp" or not _cfg("SMTP_HOST"):
        line = f"[RentKart dev EMAIL] to={recipient} subject={subject!r}\n{body}"
        logger.warning(line)
        print(line, flush=True)
        return True, "logged in console"

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    try:
        host = str(_cfg("SMTP_HOST"))
        port = int(_cfg("SMTP_PORT", 587) or 587)
        username = str(_cfg("SMTP_USERNAME", ""))
        password = str(_cfg("SMTP_PASSWORD", ""))
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            if str(_cfg("SMTP_USE_TLS", "true")).lower() in ("1", "true", "yes", "on"):
                server.starttls()
        if username:
            server.login(username, password)
        server.send_message(message)
        server.quit()
        return True, "sent"
    except Exception as exc:  # noqa: BLE001 - notifications must not break flows
        logger.error("SMTP send failed: %s", type(exc).__name__)
        return False, "Could not send email"


def send_otp_email(to_email, code, purpose="signup", minutes=None) -> tuple:
    minutes = minutes or int(_cfg("OTP_EXPIRY_MINUTES", 5) or 5)
    action = PURPOSE_LABELS.get(purpose, "verify your account")
    body = (f"Your RentKart verification code is {code}.\n\n"
            f"Use it to {action}. The code expires in {minutes} minutes and can "
            "only be used once.\n\n"
            "If you did not request this code, you can ignore this email.")
    return send_email(to_email, "Your RentKart verification code", body)


def send_sms(phone, text) -> tuple:
    from utils.sms import send_text
    result = send_text(phone, text)
    return bool(result), result.message


def _money(value):
    try:
        return f"Rs {float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return f"Rs {value}"


def booking_confirmed(booking) -> list:
    """Best-effort confirmation to renter and owner; returns log lines sent."""
    item = getattr(booking, "item", None)
    title = getattr(item, "title", "your rental")
    lines = []
    renter = getattr(booking, "renter", None)
    owner = getattr(item, "owner", None) if item else None
    summary = (f"Booking {booking.order_id or booking.id} for {title} is confirmed. "
               f"Dates: {booking.start_date} to {booking.end_date}. "
               f"Total: {_money(booking.total_payable)}.")
    if renter is not None:
        if renter.email:
            send_email(renter.email, "RentKart booking confirmed", summary)
            lines.append(f"email:{renter.email}")
        if renter.phone:
            send_sms(renter.phone, summary)
            lines.append(f"sms:{renter.phone}")
    if owner is not None and owner.phone:
        owner_text = (f"New confirmed booking {booking.order_id or booking.id} for {title}. "
                      f"Dates: {booking.start_date} to {booking.end_date}.")
        send_sms(owner.phone, owner_text)
        lines.append(f"sms:{owner.phone}")
    return lines


def cancellation_notice(booking, actor_label="user", reason="") -> list:
    item = getattr(booking, "item", None)
    title = getattr(item, "title", "your rental")
    lines = []
    text = (f"Booking {booking.order_id or booking.id} for {title} was cancelled "
            f"by the {actor_label}.")
    if reason:
        text += f" Reason: {reason}."
    renter = getattr(booking, "renter", None)
    if renter is not None:
        if renter.email:
            send_email(renter.email, "RentKart booking cancelled", text)
            lines.append(f"email:{renter.email}")
        if renter.phone:
            send_sms(renter.phone, text)
            lines.append(f"sms:{renter.phone}")
    return lines


def refund_notice(booking, amount) -> list:
    renter = getattr(booking, "renter", None)
    if renter is None:
        return []
    text = (f"Refund of {_money(amount)} for booking "
            f"{booking.order_id or booking.id} has been initiated.")
    if renter.email:
        send_email(renter.email, "RentKart refund initiated", text)
    if renter.phone:
        send_sms(renter.phone, text)
    return [text]

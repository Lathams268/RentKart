"""OTP generation, hashing, phone checks, and Fast2SMS delivery for RentKart."""
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from collections import defaultdict

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"
PHONE_RE = re.compile(r"^[6-9]\d{9}$")
_send_log = defaultdict(list)


class SMSResult:
    """Boolean-true on success and unpacks as (ok, message)."""

    def __init__(self, success: bool, message: str = ""):
        self.success = bool(success)
        self.message = str(message)

    def __bool__(self):
        return self.success

    def __iter__(self):
        return iter((self.success, self.message))

    def __getitem__(self, index):
        return (self.success, self.message)[index]

    def __repr__(self):
        return f"SMSResult(success={self.success}, message={self.message!r})"

    def __eq__(self, other):
        if isinstance(other, bool):
            return self.success == other
        if isinstance(other, tuple):
            return (self.success, self.message) == other
        return super().__eq__(other)


def _cfg(key, default=None):
    env_val = os.environ.get(key)
    if env_val is not None and env_val != "":
        return env_val
    if has_app_context():
        val = current_app.config.get(key)
        if val is not None and val != "":
            return val
    return default


def _cfg_int(key, default):
    try:
        return int(_cfg(key, default))
    except (TypeError, ValueError):
        return int(default)


def normalize_phone(phone: str):
    """Strip +91, spaces and a leading 0; return 10-digit number or None."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone).strip())
    if digits.startswith("91") and len(digits) >= 12:
        digits = digits[-10:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if PHONE_RE.match(digits):
        return digits
    return None


def generate_otp(length=None) -> str:
    """Return a new cryptographically random numeric OTP."""
    n = int(length or _cfg_int("OTP_LENGTH", 4))
    n = max(4, min(n, 8))
    return "".join(secrets.choice("0123456789") for _ in range(n))


def hash_otp(otp: str, secret=None) -> str:
    """HMAC-SHA256 hex digest of the OTP using SECRET_KEY."""
    key = secret if secret is not None else _cfg("SECRET_KEY", "")
    if isinstance(key, bytes):
        key_bytes = key
    else:
        key_bytes = str(key or "").encode("utf-8")
    return hmac.new(key_bytes, str(otp or "").encode("utf-8"), hashlib.sha256).hexdigest()


def otp_matches(otp: str, digest: str) -> bool:
    if not digest or otp is None:
        return False
    return hmac.compare_digest(hash_otp(otp), str(digest))


def _friendly_error(provider_text: str, fallback="other") -> str:
    text = str(provider_text or "").lower()
    if not text and fallback == "not_configured":
        return "SMS service is not configured"
    if "not configured" in text or fallback == "not_configured":
        return "SMS service is not configured"
    if fallback == "unreachable" or "timeout" in text or "timed out" in text or "unreachable" in text:
        return "SMS service is unreachable. Please try again."
    if "balance" in text or "insufficient" in text:
        return "Insufficient SMS balance. Please top up and try again."
    if "invalid" in text and "number" in text:
        return "That mobile number could not receive SMS."
    if "route" in text and ("not" in text or "invalid" in text or "enable" in text):
        return "SMS route is not enabled for this account."
    if fallback == "invalid_number":
        return "That mobile number could not receive SMS."
    return "Could not send OTP. Please try again."


def _log_provider(message: str):
    """Log provider text without API key or OTP digits-as-code."""
    logger.error("Fast2SMS provider: %s", message)
    print("Fast2SMS provider:", message, flush=True)


def send_sms_otp(phone: str, otp: str):
    """
    POST OTP to Fast2SMS. Returns SMSResult / (ok, message).
    Never logs the OTP or the API key.
    """
    normalized = normalize_phone(phone)
    if not normalized:
        raw = re.sub(r"\D", "", str(phone or ""))
        if not raw or len(raw) < 10:
            return SMSResult(False, "Invalid phone number. Please enter a valid 10-digit mobile number.")
        return SMSResult(False, "Please enter a valid 10-digit Indian mobile number.")

    api_key = _cfg("SMS_API_KEY", "") or ""
    otp_mode = str(_cfg("OTP_MODE", "sms") or "sms").lower()

    if otp_mode == "demo":
        return SMSResult(True, "OTP sent successfully in demo mode.")

    if not api_key:
        return SMSResult(False, "SMS service is not configured")

    route = str(_cfg("FAST2SMS_ROUTE", "otp") or "otp").lower()
    expiry = _cfg_int("OTP_EXPIRY_MINUTES", 5)
    headers = {"authorization": str(api_key)}
    if route == "q":
        payload = {
            "route": "q",
            "message": f"Your RentKart OTP is {otp}. Valid for {expiry} minutes. Do not share it.",
            "language": "english",
            "numbers": normalized,
        }
    else:
        payload = {
            "route": "otp",
            "variables_values": otp,
            "numbers": normalized,
        }

    try:
        import requests
        resp = requests.post(FAST2SMS_URL, data=payload, headers=headers, timeout=10)
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}
        provider_msg = body.get("message") or body.get("error") or resp.text or ""
        if isinstance(provider_msg, list):
            provider_msg = " ".join(str(x) for x in provider_msg)
        if body.get("return") is True:
            return SMSResult(True, "OTP sent successfully.")
        _log_provider(str(provider_msg)[:500])
        return SMSResult(False, _friendly_error(str(provider_msg)))
    except Exception as exc:
        name = type(exc).__name__
        if "Timeout" in name or "timeout" in str(exc).lower() or "Connection" in name:
            _log_provider("unreachable")
            return SMSResult(False, _friendly_error("", fallback="unreachable"))
        _log_provider(name)
        return SMSResult(False, _friendly_error(str(exc)))


def prune_send_log(now=None):
    now = now or time.time()
    window = _cfg_int("OTP_SEND_WINDOW_MINUTES", 10) * 60
    for key, stamps in list(_send_log.items()):
        _send_log[key] = [t for t in stamps if now - t < window]
        if not _send_log[key]:
            _send_log.pop(key, None)


def record_send(phone: str, ip: str):
    now = time.time()
    prune_send_log(now)
    if phone:
        _send_log[f"phone:{phone}"].append(now)
    if ip:
        _send_log[f"ip:{ip}"].append(now)


def sends_remaining(phone: str, ip: str) -> int:
    prune_send_log()
    limit = _cfg_int("OTP_MAX_SENDS", 3)
    used_phone = len(_send_log.get(f"phone:{phone}", []))
    used_ip = len(_send_log.get(f"ip:{ip}", [])) if ip else 0
    return max(0, limit - max(used_phone, used_ip))


def rate_limited(phone: str, ip: str) -> bool:
    return sends_remaining(phone, ip) <= 0


def reset_rate_limits():
    _send_log.clear()

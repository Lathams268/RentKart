"""Database-backed OTP lifecycle shared by signup, phone login, number changes
and password reset.

Rules enforced here (all configurable, see config.py):
* 6-digit numeric code, stored only as an HMAC hash.
* 5 minute expiry.
* 5 wrong attempts, then the code locks for 15 minutes.
* Resends: 30 second cooldown, at most 5 sends per hour per target; every new
  code supersedes the previous one so old codes can never be replayed.
* ``OTP_MODE=console`` prints the code to the server log and returns it to the
  caller so development works without an SMS provider.
"""
import os
from datetime import datetime, timedelta

from flask import current_app, has_app_context

from models import db, OtpCode
from utils.otp import generate_otp, hash_otp, otp_matches

STATUS_OK = "ok"
STATUS_INVALID = "invalid"
STATUS_EXPIRED = "expired"
STATUS_LOCKED = "locked"
STATUS_MISSING = "missing"


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


def dev_mode() -> bool:
    return str(_cfg("OTP_MODE", "console")).lower() in ("console", "demo", "dev")


def normalize_target(channel, target) -> str:
    value = str(target or "").strip()
    if channel == "email":
        return value.lower()
    return value


class IssueResult:
    def __init__(self, ok, message="", code=None, retry_after=0):
        self.ok = bool(ok)
        self.message = str(message)
        self.code = code
        self.retry_after = int(retry_after or 0)

    def __bool__(self):
        return self.ok

    def __iter__(self):
        return iter((self.ok, self.message))

    def __repr__(self):
        return f"IssueResult(ok={self.ok}, message={self.message!r}, retry={self.retry_after})"


class VerifyResult:
    def __init__(self, status, message="", remaining=0, locked_seconds=0):
        self.status = status
        self.message = str(message)
        self.remaining = max(0, int(remaining or 0))
        self.locked_seconds = max(0, int(locked_seconds or 0))

    @property
    def ok(self):
        return self.status == STATUS_OK

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"VerifyResult(status={self.status!r}, remaining={self.remaining})"


def _latest(purpose, channel, target):
    return (OtpCode.query
            .filter_by(purpose=purpose, channel=channel, target=target)
            .order_by(OtpCode.created_at.desc(), OtpCode.id.desc())
            .first())


def latest_active(purpose, channel, target):
    normalized = normalize_target(channel, target)
    return (OtpCode.query
            .filter_by(purpose=purpose, channel=channel, target=normalized)
            .filter(OtpCode.consumed_at.is_(None), OtpCode.superseded_at.is_(None))
            .order_by(OtpCode.created_at.desc(), OtpCode.id.desc())
            .first())


def cooldown_remaining(purpose, channel, target, now=None) -> int:
    """Seconds the user must still wait before another send (0 = ready)."""
    now = now or datetime.utcnow()
    normalized = normalize_target(channel, target)
    last = _latest(purpose, channel, normalized)
    if not last or not last.created_at:
        return 0
    wait = _cfg_int("OTP_RESEND_SECONDS", 30)
    elapsed = (now - last.created_at).total_seconds()
    return max(0, int(wait - elapsed))


def sends_used(channel, target, now=None) -> int:
    now = now or datetime.utcnow()
    window = _cfg_int("OTP_SEND_WINDOW_MINUTES", 60) * 60
    since = now - timedelta(seconds=window)
    normalized = normalize_target(channel, target)
    return (OtpCode.query
            .filter_by(channel=channel, target=normalized)
            .filter(OtpCode.created_at >= since)
            .count())


def issue_otp(user, purpose, channel, target, ip_address=None,
              enforce_cooldown=False, minutes=None, code=None) -> IssueResult:
    """Create, store and deliver a new OTP, superseding any active one."""
    purpose = str(purpose or "")
    channel = str(channel or "sms").lower()
    target = normalize_target(channel, target)
    if purpose not in OtpCode.PURPOSES:
        return IssueResult(False, "Unknown verification purpose.")
    if channel not in OtpCode.CHANNELS:
        return IssueResult(False, "Unknown verification channel.")
    if not target:
        return IssueResult(False, "A phone number or email is required.")

    now = datetime.utcnow()
    if enforce_cooldown:
        wait = cooldown_remaining(purpose, channel, target, now)
        if wait > 0:
            return IssueResult(False, f"Please wait {wait}s before requesting a new code.",
                               retry_after=wait)

    max_sends = _cfg_int("OTP_MAX_SENDS", 5)
    if sends_used(channel, target, now) >= max_sends:
        window = _cfg_int("OTP_SEND_WINDOW_MINUTES", 60)
        return IssueResult(
            False,
            f"Too many codes requested for this {'email' if channel == 'email' else 'number'}. "
            f"Try again after {window} minutes.",
            retry_after=window * 60,
        )

    # Invalidate every previously active code for this purpose+target.
    (OtpCode.query
     .filter_by(purpose=purpose, channel=channel, target=target)
     .filter(OtpCode.consumed_at.is_(None), OtpCode.superseded_at.is_(None))
     .update({"superseded_at": now}, synchronize_session=False))

    expiry_minutes = int(minutes or _cfg_int("OTP_EXPIRY_MINUTES", 5))
    length = _cfg_int("OTP_LENGTH", 6)
    code = str(code or generate_otp(length))
    row = OtpCode(
        user_id=getattr(user, "id", user) or None,
        purpose=purpose,
        channel=channel,
        target=target,
        code_hash=hash_otp(code),
        expires_at=now + timedelta(minutes=expiry_minutes),
        max_attempts=_cfg_int("OTP_MAX_ATTEMPTS", 5),
        ip_address=(ip_address or "")[:60] or None,
    )
    db.session.add(row)
    db.session.commit()

    if channel == "email":
        from utils.notify import send_otp_email
        ok, message = send_otp_email(target, code, purpose, expiry_minutes)
    else:
        from utils.sms import send_otp
        result = send_otp(target, code, expiry_minutes)
        ok, message = bool(result), result.message

    if not ok:
        # The code never reached the user: retire it so it cannot be guessed in.
        row.superseded_at = datetime.utcnow()
        db.session.commit()
        return IssueResult(False, message or "Could not send the verification code.")

    debug_code = code if dev_mode() else None
    text = "Verification code sent."
    if debug_code:
        text = f"Dev mode: your code is {debug_code} (also printed in the server log)."
    return IssueResult(True, text, code=debug_code)


def verify_otp(purpose, channel, target, code, consume=True) -> VerifyResult:
    """Check a submitted code, counting failures and enforcing the lock."""
    channel = str(channel or "sms").lower()
    target = normalize_target(channel, target)
    code = str(code or "").strip()
    now = datetime.utcnow()

    row = latest_active(purpose, channel, target)
    if row is None:
        latest = _latest(purpose, channel, target)
        if latest is not None and latest.consumed_at is not None:
            return VerifyResult(STATUS_MISSING,
                                "This code was already used. Please request a new one.")
        return VerifyResult(STATUS_MISSING, "No active code found. Please request a new one.")

    if row.is_locked(now):
        seconds = int((row.locked_until - now).total_seconds())
        return VerifyResult(STATUS_LOCKED,
                            f"Too many wrong attempts. Try again in {max(1, seconds // 60)} minutes.",
                            locked_seconds=seconds)

    if row.locked_until and row.locked_until <= now:
        # Lock expired: give the user a fresh set of attempts.
        row.locked_until = None
        row.attempts = 0
        db.session.commit()

    if row.expires_at <= now:
        return VerifyResult(STATUS_EXPIRED, "This code has expired. Please request a new one.")

    if not otp_matches(code, row.code_hash):
        row.attempts = int(row.attempts or 0) + 1
        if row.attempts >= int(row.max_attempts or 5):
            row.locked_until = now + timedelta(minutes=_cfg_int("OTP_LOCK_MINUTES", 15))
            db.session.commit()
            return VerifyResult(
                STATUS_LOCKED,
                "Too many wrong attempts. Please try again in 15 minutes.",
                locked_seconds=_cfg_int("OTP_LOCK_MINUTES", 15) * 60,
            )
        db.session.commit()
        left = max(0, int(row.max_attempts or 5) - row.attempts)
        return VerifyResult(STATUS_INVALID, f"Wrong code. {left} attempts left.", remaining=left)

    if consume:
        row.consumed_at = now
        db.session.commit()
    return VerifyResult(STATUS_OK, "Verified.")


def clear_pending(purpose, channel, target):
    """Retire codes when a flow is abandoned (e.g. changing the target number)."""
    normalized = normalize_target(channel, target)
    (OtpCode.query
     .filter_by(purpose=purpose, channel=channel, target=normalized)
     .filter(OtpCode.consumed_at.is_(None), OtpCode.superseded_at.is_(None))
     .update({"superseded_at": datetime.utcnow()}, synchronize_session=False))
    db.session.commit()

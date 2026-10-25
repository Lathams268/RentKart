"""SMS delivery behind a small swappable provider interface.

Providers
---------
``console``   development: prints the message in the server terminal, never sends
``msg91``     MSG91 Flow API - India, needs a DLT-approved template id
``twilio``    Twilio programmable SMS - E.164 numbers, optional messaging service
``fast2sms``  legacy Fast2SMS quick route (kept for existing deployments)

``OTP_MODE=console|demo|dev`` always forces the console provider so development
and the test suite never spend money on SMS. With ``OTP_MODE=sms`` the provider
named by ``SMS_PROVIDER`` is used and every credential is read from the
environment / app config (see README "Switch from console to real SMS").
No key is ever hard-coded.
"""
import logging
import os
import re

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"
TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
MSG91_URL = "https://control.msg91.com/api/v5/flow/"

# Shown in the UI whenever OTP_MODE=console.
DEV_OTP_NOTICE = "Dev mode: OTP is printed in the server terminal."


class SmsResult:
    """Boolean-true on success and unpacks as ``(ok, message)``."""

    def __init__(self, ok, message="", provider=""):
        self.ok = bool(ok)
        self.message = str(message)
        self.provider = str(provider)

    def __bool__(self):
        return self.ok

    def __iter__(self):
        return iter((self.ok, self.message))

    def __getitem__(self, index):
        return (self.ok, self.message)[index]

    def __repr__(self):
        return f"SmsResult(ok={self.ok}, provider={self.provider!r}, message={self.message!r})"


def _cfg(key, default=""):
    env_val = os.environ.get(key)
    if env_val is not None and env_val != "":
        return env_val
    if has_app_context():
        val = current_app.config.get(key)
        if val is not None and val != "":
            return val
    if default == "":
        import config
        return getattr(config, key, "")
    return default


def _cfg_int(key, default):
    try:
        return int(_cfg(key, default))
    except (TypeError, ValueError):
        return int(default)


# --------------------------------------------------------------------------- #
# Phone helpers: India first, but any +CC number is accepted for Twilio.
# --------------------------------------------------------------------------- #
def only_digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def to_e164(phone, default_dial="+91") -> str:
    """Return ``+919876543210`` for Indian input, ``+<cc>...`` for international.

    Empty string means the value cannot be turned into a dialable number.
    """
    raw = str(phone or "").strip()
    if not raw:
        return ""
    dial = "+" + only_digits(default_dial) if default_dial else "+91"
    if raw.startswith("+"):
        number = only_digits(raw)
        return ("+" + number) if 8 <= len(number) <= 15 else ""
    number = only_digits(raw)
    if len(number) == 10:
        return dial + number
    if len(number) == 11 and number.startswith("0"):
        return dial + number[1:]
    if len(number) == 12 and number.startswith(dial.lstrip("+")):
        return "+" + number
    if 8 <= len(number) <= 15:
        return "+" + number
    return ""


def msg91_mobile(phone) -> str:
    """MSG91 expects the number with country code and no plus sign."""
    return to_e164(phone).lstrip("+")


def otp_message(code, minutes) -> str:
    return (f"Your RentKart OTP is {code}. It is valid for {minutes} minutes. "
            "Do not share it with anyone.")


def _console(phone, text, kind="SMS"):
    line = f"[RentKart dev {kind}] to={phone} :: {text}"
    logger.warning(line)
    print(line, flush=True)
    return SmsResult(True, "logged in console", provider="console")


def _not_configured(provider, keys):
    return SmsResult(
        False,
        f"SMS service is not configured. Set {keys} in .env (SMS_PROVIDER={provider}).",
        provider,
    )


def _http_failure(provider, status, detail=""):
    """Turn a provider response into a message a renter can understand."""
    detail = re.sub(r"\s+", " ", str(detail or "")).strip()
    if status in (401, 403):
        return SmsResult(
            False,
            f"SMS provider {provider} rejected the API key (HTTP {status}). "
            "Check the key in .env.",
            provider,
        )
    if status == 429:
        return SmsResult(
            False,
            f"SMS provider {provider} is rate limiting us. Please try again in a minute.",
            provider,
        )
    if detail:
        return SmsResult(False, f"SMS could not be sent: {detail[:160]}", provider)
    return SmsResult(
        False,
        f"SMS provider {provider} failed (HTTP {status}). Please try again.",
        provider,
    )


def _network_failure(provider, exc):
    name = type(exc).__name__
    logger.error("%s SMS error: %s: %s", provider, name, str(exc)[:300])
    if "Timeout" in name or "Connection" in name or "SSL" in name:
        return SmsResult(
            False,
            "SMS service is unreachable. Please try again or use email login.",
            provider,
        )
    return SmsResult(False, "Could not send SMS. Please try again.", provider)


def _json_body(resp):
    try:
        return resp.json() if resp.content else {}
    except Exception:
        return {}


class BaseProvider:
    name = "base"

    def config_hint(self) -> str:
        """Empty string when ready, otherwise what is missing from .env."""
        return ""

    def ready(self):
        hint = self.config_hint()
        return (not hint, hint)

    def send_text(self, phone, text):
        raise NotImplementedError

    def send_otp(self, phone, text, code=None):
        return self.send_text(phone, text)


class ConsoleProvider(BaseProvider):
    name = "console"

    def send_text(self, phone, text):
        return _console(phone, text)

    def send_otp(self, phone, text, code=None):
        return _console(phone, text, kind="OTP")


class Fast2SmsProvider(BaseProvider):
    """Fast2SMS quick-send route. Best for Indian numbers; templates must be DLT-approved."""

    name = "fast2sms"

    def config_hint(self):
        if not (_cfg("SMS_API_KEY", "") or _cfg("FAST2SMS_API_KEY", "")):
            return "SMS service is not configured. Set FAST2SMS_API_KEY in .env."
        return ""

    def send_text(self, phone, text):
        ready, hint = self.ready()
        if not ready:
            return SmsResult(False, hint, self.name)
        digits = only_digits(phone)
        if digits.startswith("91") and len(digits) > 10:
            digits = digits[-10:]
        try:
            import requests
            resp = requests.post(
                FAST2SMS_URL,
                data={"route": "q", "message": text, "language": "english", "numbers": digits},
                headers={"authorization": str(_cfg("SMS_API_KEY") or _cfg("FAST2SMS_API_KEY"))},
                timeout=10,
            )
            body = _json_body(resp)
            if body.get("return") is True:
                return SmsResult(True, "SMS sent", self.name)
            detail = body.get("message") or body.get("error") or resp.text or ""
            logger.error("Fast2SMS error: %s", str(detail)[:300])
            return _http_failure(self.name, resp.status_code, detail)
        except Exception as exc:  # network errors
            return _network_failure(self.name, exc)


class TwilioProvider(BaseProvider):
    name = "twilio"

    def config_hint(self):
        sid = _cfg("TWILIO_ACCOUNT_SID")
        token = _cfg("TWILIO_AUTH_TOKEN")
        sender = _cfg("TWILIO_PHONE_NUMBER") or _cfg("TWILIO_MESSAGING_SERVICE_SID")
        missing = [key for key, val in (
            ("TWILIO_ACCOUNT_SID", sid),
            ("TWILIO_AUTH_TOKEN", token),
            ("TWILIO_PHONE_NUMBER (or TWILIO_MESSAGING_SERVICE_SID)", sender),
        ) if not val]
        if missing:
            return "SMS service is not configured. Set " + ", ".join(missing) + " in .env."
        return ""

    def send_text(self, phone, text):
        ready, hint = self.ready()
        if not ready:
            return SmsResult(False, hint, self.name)
        sid = _cfg("TWILIO_ACCOUNT_SID")
        token = _cfg("TWILIO_AUTH_TOKEN")
        sender = _cfg("TWILIO_PHONE_NUMBER")
        service = _cfg("TWILIO_MESSAGING_SERVICE_SID")
        to_number = to_e164(phone)
        if not to_number:
            return SmsResult(False, "Enter a valid mobile number with country code (+91...).", self.name)
        data = {"To": to_number, "Body": text}
        if service:
            data["MessagingServiceSid"] = service
        else:
            data["From"] = to_e164(sender) or sender
        try:
            import requests
            resp = requests.post(
                TWILIO_URL.format(sid=sid),
                data=data,
                auth=(sid, token),
                timeout=10,
            )
            if resp.status_code < 400:
                return SmsResult(True, "SMS sent", self.name)
            body = _json_body(resp)
            detail = body.get("message") or resp.text or ""
            logger.error("Twilio error %s: %s", resp.status_code, str(detail)[:300])
            return _http_failure(self.name, resp.status_code, detail)
        except Exception as exc:
            return _network_failure(self.name, exc)


class Msg91Provider(BaseProvider):
    """MSG91 Flow API. ``MSG91_TEMPLATE_ID`` must be a DLT-approved template.

    The template has one variable (``MSG91_OTP_VARIABLE``, default ``OTP``) that
    receives the 6-digit code. ``MSG91_SENDER_ID`` is optional and must be the
    DLT-registered 6-character sender id.
    """

    name = "msg91"

    def config_hint(self):
        missing = [key for key in ("MSG91_AUTH_KEY", "MSG91_TEMPLATE_ID") if not _cfg(key)]
        if missing:
            return "SMS service is not configured. Set " + " and ".join(missing) + " in .env."
        return ""

    def send_text(self, phone, text, code=None):
        ready, hint = self.ready()
        if not ready:
            return SmsResult(False, hint, self.name)
        mobile = msg91_mobile(phone)
        if not mobile:
            return SmsResult(False, "Enter a valid mobile number with country code (+91...).", self.name)
        variable = _cfg("MSG91_OTP_VARIABLE", "OTP") or "OTP"
        recipient = {"mobiles": mobile, variable: str(code or "")}
        payload = {
            "template_id": _cfg("MSG91_TEMPLATE_ID"),
            "short_url": "0",
            "recipients": [recipient],
        }
        sender = _cfg("MSG91_SENDER_ID")
        if sender:
            payload["sender"] = sender
        try:
            import requests
            resp = requests.post(
                MSG91_URL,
                json=payload,
                headers={"authkey": _cfg("MSG91_AUTH_KEY"), "Content-Type": "application/json"},
                timeout=10,
            )
            body = _json_body(resp)
            kind = str(body.get("type") or "").lower()
            if resp.status_code < 400 and kind != "error":
                return SmsResult(True, "SMS sent", self.name)
            detail = body.get("message") or body.get("error") or resp.text or ""
            logger.error("MSG91 error %s: %s", resp.status_code, str(detail)[:300])
            return _http_failure(self.name, resp.status_code, detail)
        except Exception as exc:
            return _network_failure(self.name, exc)

    def send_otp(self, phone, text, code=None):
        """MSG91 templates take the code as a variable, not in the body text."""
        return self.send_text(phone, text, code=code)


PROVIDERS = {
    "console": ConsoleProvider,
    "dev": ConsoleProvider,
    "demo": ConsoleProvider,
    "fast2sms": Fast2SmsProvider,
    "twilio": TwilioProvider,
    "msg91": Msg91Provider,
}


def dev_mode() -> bool:
    return str(_cfg("OTP_MODE", "console")).lower() in ("console", "demo", "dev")


def provider_name() -> str:
    if dev_mode():
        return "console"
    return str(_cfg("SMS_PROVIDER", "msg91")).lower()


def get_provider() -> BaseProvider:
    return PROVIDERS.get(provider_name(), Msg91Provider)()


def provider_status() -> dict:
    """Mode + provider readiness, used by the UI and the README examples."""
    if dev_mode():
        return {"mode": "console", "provider": "console", "ready": True,
                "message": DEV_OTP_NOTICE}
    prov = get_provider()
    ready, hint = prov.ready()
    return {"mode": "sms", "provider": prov.name, "ready": ready,
            "message": "" if ready else hint}


def send_text(phone, text) -> SmsResult:
    """Send a plain SMS; never raises."""
    if not phone:
        return SmsResult(False, "Missing phone number")
    if dev_mode():
        return _console(phone, text)
    return get_provider().send_text(phone, text)


def send_otp(phone, code, minutes=None) -> SmsResult:
    """Send an OTP SMS. In console mode the code is printed in the server terminal."""
    minutes = minutes or _cfg_int("OTP_EXPIRY_MINUTES", 5)
    text = otp_message(code, minutes)
    if dev_mode():
        return _console(phone, text, kind="OTP")
    return get_provider().send_otp(phone, text, code=str(code))

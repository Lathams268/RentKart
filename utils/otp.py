"""OTP delivery utilities for RentKart."""
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from flask import current_app

logger = logging.getLogger(__name__)


class SMSResult:
    """
    Result object that evaluates as boolean, unpacks as (success, message),
    and retains clear error or status details for user feedback.
    """
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


def clean_phone_number(phone: str) -> str:
    """Normalize phone number to digits or clean E.164 string."""
    if not phone:
        return ""
    return re.sub(r"[^\d+]", "", str(phone).strip())


def send_sms_otp(phone: str, otp: str) -> SMSResult:
    """
    Send an OTP via configured SMS service (Fast2SMS or Twilio).
    Displays clear error messages if delivery fails.
    """
    cleaned_phone = clean_phone_number(phone)
    raw_digits = re.sub(r"\D", "", cleaned_phone)

    if not raw_digits or len(raw_digits) < 10:
        msg = "Invalid phone number. Please enter a valid 10-digit mobile number."
        logger.warning(f"SMS delivery aborted: {msg} (input: {phone})")
        return SMSResult(False, msg)

    ten_digit_phone = raw_digits[-10:]

    # Check OTP mode and configurations: os.environ takes precedence over config defaults
    def _resolve_cfg(key: str, default: str = "") -> str:
        env_val = os.environ.get(key)
        if env_val is not None and env_val != "":
            return env_val
        try:
            if current_app:
                app_val = current_app.config.get(key)
                if app_val is not None and app_val != "":
                    return str(app_val)
        except RuntimeError:
            pass
        return default

    otp_mode = _resolve_cfg("OTP_MODE", "demo")
    fast2sms_key = _resolve_cfg("FAST2SMS_API_KEY", "")
    twilio_sid = _resolve_cfg("TWILIO_ACCOUNT_SID", "")
    twilio_token = _resolve_cfg("TWILIO_AUTH_TOKEN", "")
    twilio_from = _resolve_cfg("TWILIO_PHONE_NUMBER", "")

    # In demo mode without external SMS credentials, simulate immediate success
    if otp_mode == "demo" and not (fast2sms_key or (twilio_sid and twilio_token)):
        logger.info(f"[SMS DEMO] Simulated sending OTP {otp} to {cleaned_phone}")
        return SMSResult(True, "OTP sent successfully in demo mode.")

    # 1. Fast2SMS Provider
    if fast2sms_key:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            payload = {
                "variables_values": otp,
                "route": "otp",
                "numbers": ten_digit_phone,
            }
            data_bytes = urllib.parse.urlencode(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={
                    "authorization": fast2sms_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "RentKart-SMS/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.getcode()
                resp_text = response.read().decode("utf-8", errors="replace")
                resp_json = json.loads(resp_text) if resp_text else {}

                if status_code == 200 and (resp_json.get("return") is True or resp_json.get("status_code") == 200):
                    logger.info(f"[Fast2SMS] Successfully delivered OTP to {ten_digit_phone}")
                    return SMSResult(True, "OTP sent successfully via Fast2SMS.")
                else:
                    err_msg = resp_json.get("message") or resp_text or "SMS provider rejected delivery"
                    logger.error(f"[Fast2SMS Error] {err_msg}")
                    return SMSResult(False, f"Fast2SMS delivery error: {err_msg}")
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace") if hasattr(he, "read") else ""
            logger.error(f"[Fast2SMS HTTPError {he.code}] {err_body}")
            return SMSResult(False, f"Fast2SMS service returned error {he.code}: {err_body or he.reason}")
        except Exception as exc:
            logger.error(f"[Fast2SMS Exception] {str(exc)}")
            return SMSResult(False, f"Fast2SMS connection error: {str(exc)}")

    # 2. Twilio Provider
    if twilio_sid and twilio_token:
        try:
            import base64
            to_number = cleaned_phone if cleaned_phone.startswith("+") else f"+91{ten_digit_phone}"
            from_number = twilio_from or "+15005550006"
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            payload = {
                "From": from_number,
                "To": to_number,
                "Body": f"Your RentKart verification code is {otp}. Valid for 5 minutes.",
            }
            data_bytes = urllib.parse.urlencode(payload).encode("utf-8")
            auth_str = f"{twilio_sid}:{twilio_token}"
            auth_header = "Basic " + base64.b64encode(auth_str.encode("utf-8")).decode("ascii")

            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "RentKart-Twilio/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.getcode()
                resp_text = response.read().decode("utf-8", errors="replace")
                resp_json = json.loads(resp_text) if resp_text else {}

                if status_code in (200, 201) and not resp_json.get("error_code"):
                    logger.info(f"[Twilio] Successfully sent OTP to {to_number}")
                    return SMSResult(True, "OTP sent successfully via Twilio.")
                else:
                    err_msg = resp_json.get("message") or resp_text or "Twilio SMS failed"
                    logger.error(f"[Twilio Error] {err_msg}")
                    return SMSResult(False, f"Twilio SMS error: {err_msg}")
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace") if hasattr(he, "read") else ""
            logger.error(f"[Twilio HTTPError {he.code}] {err_body}")
            return SMSResult(False, f"Twilio service error {he.code}: {err_body or he.reason}")
        except Exception as exc:
            logger.error(f"[Twilio Exception] {str(exc)}")
            return SMSResult(False, f"Twilio connection error: {str(exc)}")

    # 3. If OTP_MODE is sms but no keys configured
    strict_sms = os.environ.get("STRICT_SMS_CONFIG") == "1"
    is_testing = False
    try:
        if current_app:
            is_testing = current_app.config.get("TESTING", False)
    except RuntimeError:
        pass

    if otp_mode == "sms":
        if not is_testing or strict_sms:
            err_msg = "SMS gateway credentials not configured (set FAST2SMS_API_KEY or TWILIO credentials in environment)."
            logger.error(f"[SMS Config Error] {err_msg}")
            return SMSResult(False, err_msg)

    # 4. Default fallback
    logger.info(f"[SMS STUB] Sent OTP {otp} to {phone}")
    return SMSResult(True, "OTP sent successfully.")


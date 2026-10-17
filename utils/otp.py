"""OTP delivery utilities for RentKart."""
import logging

logger = logging.getLogger(__name__)


def send_sms_otp(phone: str, otp: str) -> bool:
    """
    Send an OTP via SMS gateway (stub for Fast2SMS, Twilio, or MSG91).

    Fast2SMS implementation example:
        import requests
        url = "https://www.fast2sms.com/dev/bulkV2"
        headers = {"authorization": os.environ.get("FAST2SMS_API_KEY", "")}
        payload = {
            "variables_values": otp,
            "route": "otp",
            "numbers": phone
        }
        res = requests.post(url, data=payload, headers=headers, timeout=5)
        return res.status_code == 200

    Twilio implementation example:
        from twilio.rest import Client
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=f"Your RentKart OTP is {otp}. Valid for 5 minutes.",
            from_=os.environ.get("TWILIO_PHONE_NUMBER"),
            to=f"+91{phone}" if not phone.startswith("+") else phone
        )
        return bool(msg.sid)
    """
    logger.info(f"[SMS STUB] Sending OTP {otp} to phone {phone}")
    return True

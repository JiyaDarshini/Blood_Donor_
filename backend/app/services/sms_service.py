import logging
import secrets
import re
import httpx
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("bloodsos.sms")


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def normalize_phone_number(phone: str) -> str:
    """Clean phone number by removing whitespace, hyphens, and brackets."""
    if not phone:
        return ""
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    return cleaned


def send_sms(to_phone: str, message: str, otp_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Dispatches SMS to target phone number using configured SMS Provider.
    Supports Twilio, Fast2SMS, and local simulation/development mode.
    """
    clean_phone = normalize_phone_number(to_phone)
    provider = (settings.SMS_PROVIDER or "none").lower().strip()

    # Twilio SMS Gateway
    if provider == "twilio" and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_PHONE:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
            data = {
                "To": clean_phone,
                "From": settings.TWILIO_FROM_PHONE,
                "Body": message
            }
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, data=data, auth=auth)
                if resp.status_code in (200, 201):
                    logger.info(f"[SMS TWILIO] Message sent successfully to {clean_phone}")
                    return {"success": True, "provider": "twilio", "message": "SMS dispatched via Twilio"}
                else:
                    logger.error(f"[SMS TWILIO ERROR] HTTP {resp.status_code}: {resp.text}")
                    return {"success": False, "provider": "twilio", "error": resp.text}
        except Exception as e:
            logger.error(f"[SMS TWILIO EXCEPTION] {e}")
            return {"success": False, "provider": "twilio", "error": str(e)}

    # Fast2SMS Gateway (Works directly on Indian mobile numbers)
    elif provider == "fast2sms" and settings.SMS_API_KEY:
        try:
            raw_digits = re.sub(r"[^\d]", "", clean_phone)
            if len(raw_digits) > 10 and raw_digits.startswith("91"):
                raw_digits = raw_digits[2:]

            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {
                "authorization": settings.SMS_API_KEY,
                "Content-Type": "application/json"
            }
            if otp_code:
                payload = {
                    "route": "otp",
                    "variables_values": otp_code,
                    "numbers": raw_digits
                }
            else:
                payload = {
                    "route": "q",
                    "message": message,
                    "language": "english",
                    "flash": 0,
                    "numbers": raw_digits
                }
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json() if resp.text else {}
                    if data.get("return") is True or "request_id" in data or "message" in data:
                        logger.info(f"[SMS FAST2SMS] Message sent successfully to {raw_digits}: {data}")
                        return {"success": True, "provider": "fast2sms", "message": "SMS dispatched via Fast2SMS"}
                    else:
                        logger.warning(f"[SMS FAST2SMS WARNING] Response: {resp.text}")
                        return {"success": False, "provider": "fast2sms", "error": resp.text}
                else:
                    logger.error(f"[SMS FAST2SMS ERROR] HTTP {resp.status_code}: {resp.text}")
                    return {"success": False, "provider": "fast2sms", "error": resp.text}
        except Exception as e:
            logger.error(f"[SMS FAST2SMS EXCEPTION] {e}")
            return {"success": False, "provider": "fast2sms", "error": str(e)}

    # Fallback / Development Simulation mode
    logger.info("=" * 64)
    logger.info("📱 [SMS GATEWAY SIMULATION (DEV/FALLBACK)]")
    logger.info(f"   To:      {clean_phone}")
    logger.info(f"   Message: {message}")
    logger.info("=" * 64)

    return {
        "success": True,
        "provider": "simulation",
        "message": f"Verification SMS simulated for {clean_phone}"
    }


def send_otp_sms(to_phone: str, otp_code: str) -> Dict[str, Any]:
    """Helper to format and send OTP verification SMS."""
    message = f"Blood SOS: Your mobile verification code is {otp_code}. Valid for 10 minutes. Do not share this OTP with anyone."
    return send_sms(to_phone, message, otp_code=otp_code)


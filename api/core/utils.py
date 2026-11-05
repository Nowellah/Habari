import hashlib
import hmac
import re
import secrets

# No 0, O, 1, I or L, so a child can read the code back without mistakes.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# Channels where the sender is a phone number. One number gets one reporter ID
# across all of them, so a child can start on USSD and follow up by SMS.
PHONE_CHANNELS = {"sms", "ussd", "voice", "whatsapp"}


def new_case_code() -> str:
    return "HB-" + "".join(secrets.choice(ALPHABET) for _ in range(6))


def normalise_msisdn(n: str) -> str:
    n = re.sub(r"[^\d+]", "", n)
    if n.startswith("0"):
        n = "+256" + n[1:]
    return n if n.startswith("+") else "+" + n


def pseudo_id(channel: str, raw: str, secret: str) -> str:
    # Chat ids are prefixed by channel so they can never collide with a phone number.
    key = ("tel:" + normalise_msisdn(raw)) if channel in PHONE_CHANNELS else f"{channel}:{raw}"
    return hmac.new(secret.encode(), key.encode(), hashlib.sha256).hexdigest()[:20]

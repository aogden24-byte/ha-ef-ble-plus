"""
Request signing for the EcoFlow consumer app's cloud API

Kept in its own module so it can be deleted without touching anything else. Without
it, login still resolves the user ID, but OMOS devices (OCEAN Pro, OCEAN Panel) can
no longer fetch their bind material and need a device token pasted by hand.
"""

import hashlib
import hmac
import secrets
import string
import time

# HTTP request-signing material for the EcoFlow consumer app (package `com.ecoflow`).
# The `/iot-service/*` endpoints reject unsigned requests: every call carries a `token`
# header (HMAC keyed by the login bearer) and an `X-Sign` header (HMAC keyed by the app
# signing-cert SHA-1 concatenated with a per-package salt returned by the app's native
# `getHttpSalt`). `/auth/login` itself is unsigned, so only device calls sign. The salt
# and cert fingerprint are fixed app-integrity constants, not user credentials.
_APP_VERSION = "6.15.0.111"
_SYS_VERSION = "13"
_PHONE_MODEL = "SM-S911B"  # common Android Build.MODEL, blends with real traffic
_PACKAGE_NAME = "com.ecoflow"
_APP_CERT_SHA1 = "3bc4556d6cefafc678995b517e0df31678da03c2"
_HTTP_SALT = "Ev7f82PUhUTNkLCo"
_X_SIGN_KEY = _APP_CERT_SHA1 + _HTTP_SALT
_NONCE_ALPHABET = string.ascii_letters + string.digits


def _hmac_sha256_hex(message: str, key: str) -> str:
    """Lowercase-hex HMAC-SHA256 of `message` under `key`, matching the app"""
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def signed_headers(
    method: str, path: str, sorted_query: str, bearer: str
) -> dict[str, str]:
    now_ms = int(time.time() * 1000)
    nonce = secrets.randbelow(900_000) + 100_000

    raw_token = bearer.replace("Bearer", "").strip()
    authorization = f"Bearer {raw_token}"

    token_msg = (
        f"phoneModel={_PHONE_MODEL}&platform=android"
        f"&sysVersion={_SYS_VERSION}&version={_APP_VERSION}"
        f"&nonce={nonce}&timestamp={now_ms}"
    )
    token_sig = _hmac_sha256_hex(token_msg, raw_token)

    x_nonce = "".join(secrets.choice(_NONCE_ALPHABET) for _ in range(8))
    x_sign_msg = f"{method}{path}{sorted_query}null{now_ms}{x_nonce}"
    x_sign = _hmac_sha256_hex(x_sign_msg, _X_SIGN_KEY).upper()

    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "platform": "android",
        "version": _APP_VERSION,
        "sysVersion": _SYS_VERSION,
        "phoneModel": _PHONE_MODEL,
        "lang": "en-us",
        "countryCode": "US",
        "nonce": str(nonce),
        "timestamp": str(now_ms),
        "token": token_sig,
        "Authorization": authorization,
        "Package": _PACKAGE_NAME,
        "X-Timestamp": str(now_ms),
        "X-Nonce": x_nonce,
        "X-Sign": x_sign,
    }

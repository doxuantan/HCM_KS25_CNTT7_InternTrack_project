import base64
import binascii
import bcrypt
import hashlib
import hmac
import json
import math
import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings


_BCRYPT_MAX_PASSWORD_BYTES = 72


class InvalidTokenError(ValueError):
    pass


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise TypeError("Password must be a string.")

    encoded = password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("Password must not exceed 72 UTF-8 bytes.")
    return encoded


def hash_password(password: str) -> str:
    password_hash = bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt())
    return password_hash.decode("ascii")


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not isinstance(plain_password, str) or not isinstance(password_hash, str):
        return False

    try:
        return bcrypt.checkpw(
            _password_bytes(plain_password),
            password_hash.encode("ascii"),
        )
    except (UnicodeEncodeError, ValueError):
        return False


def _signing_key() -> bytes:
    key = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    if len(key) < 32:
        raise ValueError("SECRET_KEY must contain at least 32 UTF-8 bytes.")
    return key


def _encode_segment(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def _decode_segment(segment: str) -> bytes:
    if not segment or any(
        character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        for character in segment
    ):
        raise InvalidTokenError("Malformed access token.")

    padded_segment = segment + "=" * (-len(segment) % 4)
    try:
        return base64.b64decode(padded_segment, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as error:
        raise InvalidTokenError("Malformed access token.") from error


def create_access_token(
    data: Mapping[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    if not isinstance(data, Mapping):
        raise TypeError("Token data must be a mapping.")

    now = datetime.now(timezone.utc)
    lifetime = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    if lifetime <= timedelta(0):
        raise ValueError("Token lifetime must be greater than zero.")

    payload = dict(data)
    payload["iat"] = int(now.timestamp())
    payload["exp"] = math.ceil((now + lifetime).timestamp())
    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}
    signing_input = f"{_encode_segment(header)}.{_encode_segment(payload)}"
    signature = hmac.new(
        _signing_key(),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{signing_input}.{encoded_signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    if not isinstance(token, str):
        raise TypeError("Access token must be a string.")

    segments = token.split(".")
    if len(segments) != 3:
        raise InvalidTokenError("Malformed access token.")

    encoded_header, encoded_payload, encoded_signature = segments
    try:
        header = json.loads(_decode_segment(encoded_header))
        payload = json.loads(_decode_segment(encoded_payload))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidTokenError("Malformed access token.") from error

    if not isinstance(header, dict) or header.get("alg") != settings.JWT_ALGORITHM:
        raise InvalidTokenError("Unsupported access token algorithm.")
    if header.get("typ") not in (None, "JWT") or not isinstance(payload, dict):
        raise InvalidTokenError("Malformed access token.")

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(
        _signing_key(),
        signing_input,
        hashlib.sha256,
    ).digest()
    supplied_signature = _decode_segment(encoded_signature)
    if not hmac.compare_digest(expected_signature, supplied_signature):
        raise InvalidTokenError("Invalid access token signature.")

    expiration = payload.get("exp")
    if (
        isinstance(expiration, bool)
        or not isinstance(expiration, (int, float))
        or not math.isfinite(expiration)
        or expiration <= time.time()
    ):
        raise InvalidTokenError("Access token has expired or has no valid expiration.")

    not_before = payload.get("nbf")
    if not_before is not None and (
        isinstance(not_before, bool)
        or not isinstance(not_before, (int, float))
        or not math.isfinite(not_before)
        or not_before > time.time()
    ):
        raise InvalidTokenError("Access token is not yet valid.")

    return payload

"""
Browser push notifications (Web Push), so alerts reach people even when the site is closed.

Implements the two standards browsers require, with libraries the project already uses:
  * RFC 8291 message encryption (aes128gcm) with `cryptography`
  * RFC 8292 VAPID sender identification, an ES256 token made with PyJWT
Off unless VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY are set (`python manage.py generate_vapid_keys`).
"""
import base64
import json
import logging
import os
import threading
import time
from urllib.parse import urlsplit

import jwt
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.db import transaction

from .models import PushSubscription

logger = logging.getLogger(__name__)

RECORD_SIZE = 4096
MAX_PAYLOAD = 3000  # stays inside one encrypted record and every push service's size limit


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def push_enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def generate_vapid_keys() -> dict:
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    private = key.private_numbers().private_value.to_bytes(32, "big")
    return {"public": b64url_encode(public), "private": b64url_encode(private)}


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt_payload(payload: bytes, p256dh: str, auth: str) -> bytes:
    """RFC 8291: encrypts `payload` for the browser that owns the p256dh/auth subscription keys."""
    receiver_public_bytes = b64url_decode(p256dh)
    auth_secret = b64url_decode(auth)
    receiver_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), receiver_public_bytes)

    sender_key = ec.generate_private_key(ec.SECP256R1())
    sender_public_bytes = sender_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    shared_secret = sender_key.exchange(ec.ECDH(), receiver_public)

    ikm = _hkdf(auth_secret, shared_secret, b"WebPush: info\x00" + receiver_public_bytes + sender_public_bytes, 32)
    salt = os.urandom(16)
    content_key = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)

    ciphertext = AESGCM(content_key).encrypt(nonce, payload + b"\x02", None)  # 0x02 marks the last record
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(sender_public_bytes)]) + sender_public_bytes
    return header + ciphertext


def _vapid_authorization(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    private_value = int.from_bytes(b64url_decode(settings.VAPID_PRIVATE_KEY), "big")
    key = ec.derive_private_key(private_value, ec.SECP256R1())
    token = jwt.encode(
        {
            "aud": f"{parts.scheme}://{parts.netloc}",
            "exp": int(time.time()) + 12 * 3600,
            "sub": f"mailto:{settings.VAPID_CONTACT_EMAIL}",
        },
        key,
        algorithm="ES256",
    )
    return f"vapid t={token}, k={settings.VAPID_PUBLIC_KEY}"


def send_to_subscription(subscription: PushSubscription, payload: dict) -> bool:
    """Sends one push message. Deletes the subscription when the browser has dropped it."""
    body = encrypt_payload(json.dumps(payload).encode()[:MAX_PAYLOAD], subscription.p256dh, subscription.auth)
    response = requests.post(
        subscription.endpoint,
        data=body,
        headers={
            "Authorization": _vapid_authorization(subscription.endpoint),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": "86400",
            "Urgency": "high",
        },
        timeout=10,
    )
    if response.status_code in (404, 410):  # unsubscribed or expired
        subscription.delete()
        return False
    if response.status_code >= 400:
        logger.warning("Push service answered %s for subscription %s", response.status_code, subscription.pk)
        return False
    return True


def deliver(user_id: int, title: str, message: str, url: str) -> int:
    """Sends to every browser the user subscribed. Returns how many were accepted."""
    sent = 0
    for subscription in PushSubscription.objects.filter(user_id=user_id):
        try:
            sent += send_to_subscription(subscription, {"title": title, "body": message, "url": url})
        except Exception:  # noqa: BLE001 - a bad subscription or network error must not break the caller
            logger.exception("Could not send push notification to subscription %s", subscription.pk)
    return sent


def push_to_user(user, title: str, message: str, url: str = "/") -> None:
    """
    Queues a push for after the current database transaction, on a background thread, so the
    request that caused the notification never waits for (or fails because of) the push service.
    """
    if not push_enabled() or not PushSubscription.objects.filter(user=user).exists():
        return
    transaction.on_commit(
        lambda: threading.Thread(target=deliver, args=(user.pk, title, message, url), daemon=True).start()
    )

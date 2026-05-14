# coding=utf-8
"""
    @project: MaxKB
    @file： encryption.py
    @desc: Fernet wrapper used by the finance module to encrypt SMTP
    passwords at rest (Gate 5 Track B).

    The Fernet key is derived deterministically from Django's
    `settings.SECRET_KEY` via SHA-256, then base64-urlsafe-encoded to the
    32-byte form Fernet expects. This means:

      * No additional secret material to deploy.
      * **Rotating `SECRET_KEY` breaks every existing SmtpConfig row** —
        passwords would have to be re-entered, since Fernet can't decrypt
        with the new key. Document this in your runbook before rotating.

    The Fernet construction is cached at module level so the SHA-256 +
    base64 work happens once per process.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    """
    Build a Fernet instance from `settings.SECRET_KEY`.

    Cached so repeated encrypt/decrypt calls don't re-hash the key on every
    invocation. Note: changing SECRET_KEY at runtime won't be picked up
    without a process restart — this is intentional, Fernet doesn't support
    key rotation in-place anyway.
    """
    raw = settings.SECRET_KEY or ''
    if not raw:
        # Fail loudly here rather than silently using an empty key — that
        # would produce identical ciphertexts across deployments.
        raise RuntimeError(
            'finance.encryption: settings.SECRET_KEY is empty; cannot derive Fernet key'
        )
    digest = hashlib.sha256(raw.encode('utf-8')).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """
    Encrypt `plaintext` with the workspace's derived Fernet key. Returns a
    base64-urlsafe ASCII string suitable for direct storage in TextField.

    Empty string is treated as a no-op and stored as empty — keeps the "no
    password set yet" case representable without nullable columns.
    """
    if plaintext is None or plaintext == '':
        return ''
    token = _fernet().encrypt(plaintext.encode('utf-8'))
    return token.decode('ascii')


def decrypt_secret(ciphertext: str) -> str:
    """
    Inverse of `encrypt_secret`. Raises `ValueError` on any decryption
    failure (invalid token, wrong key, corrupted bytes) — callers are
    expected to translate that into a user-facing message.
    """
    if ciphertext is None or ciphertext == '':
        return ''
    try:
        plaintext = _fernet().decrypt(ciphertext.encode('ascii'))
    except (InvalidToken, ValueError, TypeError) as e:
        raise ValueError(f'failed to decrypt secret: {e!r}') from e
    return plaintext.decode('utf-8')

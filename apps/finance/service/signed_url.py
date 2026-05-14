# coding=utf-8
"""
    @project: MaxKB
    @file： signed_url.py
    @desc: Generate / verify signed download URLs for large finance
    attachments (Gate 6 Track C / C1).

    The token is a `django.core.signing.dumps()` payload — same HMAC
    construction Django uses for its session signer, keyed on
    ``settings.SECRET_KEY``. That gives us:

      * tamper-evidence (any byte flip → `BadSignature`)
      * built-in expiry (we verify via `signing.loads(..., max_age=...)`)
      * no extra DB table — the URL is self-contained

    The signed payload intentionally carries the OSS key directly so the
    view layer can stream the file without an extra lookup. Workspace +
    target_type / target_id are included for audit-logging downstream.

    Public surface:
      * ``make_signed_download_url(...)`` → relative URL ``/admin/api/finance/download/<token>``
      * ``decode_signed_token(token, max_age)`` → dict on success, raises
        ``BadSignature`` / ``SignatureExpired`` on tamper / expiry.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from django.conf import settings
from django.core import signing


# Tag the signer salt so a token minted here cannot accidentally be
# verified against a different Django signer (e.g. session cookies).
_SIGNER_SALT = 'finance.signed_download.v1'

# Default lifetime — 7 days. Long enough that an investor can pick up
# their materials over a weekend without us re-issuing, short enough
# that a leaked URL self-heals.
DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60


def _coerce(value: Any) -> str:
    """Normalise UUIDs / ints / strings for stable JSON-friendly payloads."""
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def make_signed_download_url(
    *,
    target_type: str,
    target_id: UUID | str,
    workspace_id: str,
    oss_key: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    base_path: str = '/admin/api/finance/download/',
) -> str:
    """
    Generate a signed URL that allows downloading the OSS resource WITHOUT
    authentication for ``ttl_seconds`` (default 7 days).

    Uses ``django.core.signing.dumps`` to encode the parameters; the
    returned URL is relative (caller can prepend a host if needed) and
    of the form::

        /admin/api/finance/download/<token>

    The token carries ``{target_type, target_id, workspace_id, oss_key}``
    plus the timestamp Django bakes into ``signing.dumps``. Server-side
    verification uses ``signing.loads(..., max_age=ttl_seconds)``.

    ``ttl_seconds`` is encoded in the payload as ``ttl`` so the view can
    pass the SAME max-age to ``signing.loads`` — without it, the view
    would have to hard-code an assumption about how long callers wanted
    the URL to live.
    """
    if not oss_key:
        raise ValueError('oss_key is required to mint a signed download URL')
    if ttl_seconds <= 0:
        raise ValueError('ttl_seconds must be positive')

    payload = {
        'target_type': str(target_type or ''),
        'target_id': _coerce(target_id),
        'workspace_id': str(workspace_id or ''),
        'oss_key': str(oss_key),
        'ttl': int(ttl_seconds),
        'v': 1,  # payload version — bump if the schema ever changes
    }
    token = signing.dumps(
        payload,
        key=settings.SECRET_KEY,
        salt=_SIGNER_SALT,
        compress=True,
    )
    # Trim trailing slash defence — base_path may or may not have one.
    if not base_path.endswith('/'):
        base_path = base_path + '/'
    return f'{base_path}{token}'


def decode_signed_token(
    token: str,
    *,
    max_age: int | None = None,
) -> dict[str, Any]:
    """
    Verify ``token`` against the finance download signer and return its
    payload.

    Raises:
        ``signing.BadSignature`` — tamper / wrong salt / wrong key
        ``signing.SignatureExpired`` — older than ``max_age`` seconds

    If ``max_age`` is None, we trust the ``ttl`` baked into the payload
    by ``make_signed_download_url``. That way callers don't have to
    remember the original lifetime — it travels with the token.
    """
    if not token:
        raise signing.BadSignature('empty token')

    # First decode without max_age to fish out the embedded ttl, then
    # re-verify with the correct max_age. signing.loads is cheap so this
    # double-decode is fine and avoids letting the caller forget the TTL.
    raw = signing.loads(token, key=settings.SECRET_KEY, salt=_SIGNER_SALT)
    effective_max_age = max_age
    if effective_max_age is None:
        ttl = raw.get('ttl') if isinstance(raw, dict) else None
        effective_max_age = int(ttl) if ttl else DEFAULT_TTL_SECONDS

    # Second pass enforces expiry. Re-using signing.loads is the canonical
    # way to validate timestamp + signature in a single call.
    payload = signing.loads(
        token,
        key=settings.SECRET_KEY,
        salt=_SIGNER_SALT,
        max_age=effective_max_age,
    )
    if not isinstance(payload, dict):
        raise signing.BadSignature('payload not a dict')
    return payload


def short_token_id(token: str) -> str:
    """
    Truncated identifier for log lines — never log full tokens (they're
    bearer credentials until they expire). Returns ``<head>..<tail>``
    so an operator can still correlate audit entries.
    """
    if not token:
        return ''
    if len(token) <= 14:
        return token[:4] + '..' + token[-2:]
    return token[:8] + '..' + token[-6:]

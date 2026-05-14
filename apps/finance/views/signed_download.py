# coding=utf-8
"""
    @project: MaxKB
    @file： signed_download.py
    @desc: Public download endpoint for signed-URL finance attachments
    (Gate 6 Track C / C1).

    Security model: there is NO session / token auth on this view.
    Security comes from the signed token, which:
      * is HMACed with ``settings.SECRET_KEY``
      * carries a built-in expiry (default 7 days)
      * embeds the OSS key directly, so a leaked URL only exposes one
        single artifact rather than any arbitrary OSS resource.

    On every download attempt we write a FinanceAuditLog row (success
    or failure) so we have a trail of who picked up what — IP +
    user_agent come from request headers since there's no user.id.
"""
from __future__ import annotations

import urllib.parse

from django.core import signing
from django.http import HttpResponse
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.exception.app_exception import AppApiException
from finance.models import FinanceAuditAction, FinanceAuditTargetType
from finance.service.audit import log_event
from finance.service.document_generator import _load_bytes
from finance.service.signed_url import decode_signed_token, short_token_id

_ZIP_MIME = 'application/zip'


def _get_ip(request: Request) -> str | None:
    """Same X-Forwarded-For preference as finance.service.audit._get_ip."""
    fwd = request.META.get('HTTP_X_FORWARDED_FOR') if request is not None else None
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') if request is not None else None


def _get_ua(request: Request) -> str:
    return (request.META.get('HTTP_USER_AGENT') or '')[:512] if request is not None else ''


class SignedDownloadView(APIView):
    """
    GET /admin/api/finance/download/<token>

    Public — verification is via the signed token itself. Decodes,
    validates signature + expiry, streams the OSS resource. Always
    audit-logs the attempt (with a truncated token id for traceability).
    """

    # Explicitly empty so neither global DEFAULT_AUTHENTICATION_CLASSES
    # nor the project's TokenAuth gate is applied. The token IS the auth.
    authentication_classes = []
    permission_classes = []

    def get(self, request: Request, token: str):
        token = (token or '').strip()

        # ---- Decode + verify ----
        try:
            payload = decode_signed_token(token)
        except signing.SignatureExpired:
            # Best-effort: we can't extract the workspace from an expired
            # token without trusting the (unverified) bytes, so the audit
            # row records only the token fingerprint and the verdict.
            log_event(
                workspace_id=None,
                actor_id=None,
                target_type=FinanceAuditTargetType.MATERIALS_TASK,
                target_id=None,
                action=FinanceAuditAction.DOWNLOAD,
                payload={
                    'result': 'expired',
                    'token_id': short_token_id(token),
                },
                ip=_get_ip(request),
                user_agent=_get_ua(request),
            )
            raise AppApiException(410, 'download link has expired')
        except signing.BadSignature:
            log_event(
                workspace_id=None,
                actor_id=None,
                target_type=FinanceAuditTargetType.MATERIALS_TASK,
                target_id=None,
                action=FinanceAuditAction.DOWNLOAD,
                payload={
                    'result': 'invalid_signature',
                    'token_id': short_token_id(token),
                },
                ip=_get_ip(request),
                user_agent=_get_ua(request),
            )
            raise AppApiException(403, 'invalid download link')

        oss_key = payload.get('oss_key')
        if not oss_key:
            log_event(
                workspace_id=payload.get('workspace_id'),
                actor_id=None,
                target_type=payload.get('target_type') or FinanceAuditTargetType.MATERIALS_TASK,
                target_id=payload.get('target_id'),
                action=FinanceAuditAction.DOWNLOAD,
                payload={'result': 'malformed_payload', 'token_id': short_token_id(token)},
                ip=_get_ip(request),
                user_agent=_get_ua(request),
            )
            raise AppApiException(400, 'malformed signed token')

        # ---- Fetch + stream ----
        try:
            blob = _load_bytes(oss_key)
        except Exception as e:  # noqa: BLE001 — bubble up as an audited 404
            log_event(
                workspace_id=payload.get('workspace_id'),
                actor_id=None,
                target_type=payload.get('target_type') or FinanceAuditTargetType.MATERIALS_TASK,
                target_id=payload.get('target_id'),
                action=FinanceAuditAction.DOWNLOAD,
                payload={
                    'result': 'oss_lookup_failed',
                    'token_id': short_token_id(token),
                    'oss_key': str(oss_key),
                    'error': repr(e),
                },
                ip=_get_ip(request),
                user_agent=_get_ua(request),
            )
            return result.error('download artifact not available', response_status=404)

        target_id = payload.get('target_id') or ''
        filename = f'materials-{target_id}.zip' if target_id else 'download.zip'
        encoded = urllib.parse.quote(filename)

        response = HttpResponse(blob, content_type=_ZIP_MIME)
        response['Content-Disposition'] = (
            f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
        )
        response['X-Content-Type-Options'] = 'nosniff'

        # Audit AFTER we have the bytes ready, so a failed OSS lookup is
        # logged separately above.
        log_event(
            workspace_id=payload.get('workspace_id'),
            actor_id=None,  # no authenticated user on this endpoint
            target_type=payload.get('target_type') or FinanceAuditTargetType.MATERIALS_TASK,
            target_id=target_id,
            action=FinanceAuditAction.DOWNLOAD,
            payload={
                'result': 'ok',
                'token_id': short_token_id(token),
                'oss_key': str(oss_key),
                'size_bytes': len(blob) if blob is not None else 0,
            },
            ip=_get_ip(request),
            user_agent=_get_ua(request),
        )
        return response

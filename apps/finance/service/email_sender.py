# coding=utf-8
"""
    @project: MaxKB
    @file： email_sender.py
    @desc: Outbound email pipeline for the Finance materials task (Gate 5
    Track B).

    Public entry points:
      * `render_template_string(text, ctx)` — sandbox-safe `{{ var }}`
        substitution; intentionally does NOT evaluate expressions.
      * `send_materials_task_email(...)` — full closure of the materials
        send: decrypt SMTP, render template, attach zip or embed link,
        write EmailSendLog (always), update task status, audit-log.

    Never raises. Errors are persisted to the EmailSendLog row and surfaced
    via the returned dict so the view layer can serialize them.
"""
from __future__ import annotations

import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any
from uuid import UUID

from django.utils import timezone

from finance.models import (
    EmailSendLog,
    EmailSendStatus,
    EmailTemplate,
    FinanceAuditAction,
    FinanceAuditTargetType,
    FinanceProject,
    MaterialsTask,
    MaterialsTaskStatus,
    SmtpConfig,
)
from finance.service.audit import log_event
from finance.service.document_generator import _load_bytes
from finance.service.encryption import decrypt_secret

_LOGGER = logging.getLogger(__name__)

# Refuse to inline-attach payloads above this. Materials zips are typically
# small (a handful of MB) — anything larger almost certainly needs a signed
# download link instead, which Gate 6 will wire up properly.
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MiB

# Conservative SMTP timeout — investor mailservers are sometimes slow but
# 30s is plenty before we should give up and ask the user to retry.
_SMTP_TIMEOUT_SECONDS = 30

# Allow `{{ var }}` with optional surrounding whitespace; identifier may be
# letters / digits / underscores / dots (for nested context like
# `project.code`).
_VAR_RE = re.compile(r'{{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*}}')


# --------------------------------------------------------------------------
# Template rendering — deliberately minimal.
# --------------------------------------------------------------------------


def render_template_string(text: str, context: dict[str, Any]) -> str:
    """
    Replace `{{ name }}` with `str(context.get(name, ''))`.

    Supports dotted lookups (`project.code` → context['project']['code'] or
    getattr(context['project'], 'code'); falls through to empty string on
    any error). Unknown variables render as empty rather than raising — the
    UI offers a preview so authors can spot typos before sending.

    NOT a full Jinja engine: no `{% if %}`, no filters, no expressions.
    """
    if not text:
        return ''

    def _resolve(path: str) -> str:
        parts = path.split('.')
        cur: Any = context
        for p in parts:
            if cur is None:
                return ''
            if isinstance(cur, dict):
                cur = cur.get(p, '')
            else:
                cur = getattr(cur, p, '')
        if cur is None:
            return ''
        return str(cur)

    return _VAR_RE.sub(lambda m: _resolve(m.group(1)), text)


# --------------------------------------------------------------------------
# Send pipeline
# --------------------------------------------------------------------------


def _local_part(addr: str) -> str:
    """Extract the local-part of an email address (before `@`)."""
    if not addr or '@' not in addr:
        return addr or ''
    return addr.split('@', 1)[0]


def _build_context(
    *,
    task: MaterialsTask,
    project: FinanceProject | None,
    to_addresses: list[str],
    zip_filename: str,
    extra_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the rendering context exposed to templates."""
    recipient_name = _local_part(to_addresses[0]) if to_addresses else ''
    ctx: dict[str, Any] = {
        'project_name': getattr(project, 'name', '') if project else '',
        'project_code': getattr(project, 'code', '') if project else '',
        'task_title': task.title,
        'recipient_name': recipient_name,
        'zip_filename': zip_filename,
    }
    if extra_context:
        # Caller-supplied wins (e.g. they can override `recipient_name` for
        # tailored sends).
        ctx.update(extra_context)
    return ctx


def _build_email(
    *,
    smtp_config: SmtpConfig,
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    body_text: str,
    body_html: str,
    zip_bytes: bytes | None,
    zip_filename: str,
) -> EmailMessage:
    """Build the MIME message; multipart/alternative when HTML present."""
    msg = EmailMessage()
    msg['From'] = formataddr(
        (smtp_config.from_name or '', smtp_config.from_email)
    )
    msg['To'] = ', '.join(to_addresses)
    if cc_addresses:
        msg['Cc'] = ', '.join(cc_addresses)
    msg['Subject'] = subject

    if body_html:
        # Plain part first (RFC 2046 — fallback for non-HTML readers).
        msg.set_content(body_text or '')
        msg.add_alternative(body_html, subtype='html')
    else:
        msg.set_content(body_text or '')

    if zip_bytes is not None:
        msg.add_attachment(
            zip_bytes,
            maintype='application',
            subtype='zip',
            filename=zip_filename,
        )
    return msg


def _dial_and_send(smtp_config: SmtpConfig, msg: EmailMessage) -> None:
    """Open the SMTP connection per config and deliver `msg`."""
    password = decrypt_secret(smtp_config.password_encrypted)

    if smtp_config.use_ssl:
        # Implicit TLS (SMTPS, classically port 465).
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            smtp_config.host,
            smtp_config.port,
            timeout=_SMTP_TIMEOUT_SECONDS,
            context=context,
        ) as client:
            if smtp_config.username:
                client.login(smtp_config.username, password)
            client.send_message(msg)
        return

    # Plain SMTP, optionally upgraded via STARTTLS.
    with smtplib.SMTP(
        smtp_config.host, smtp_config.port, timeout=_SMTP_TIMEOUT_SECONDS
    ) as client:
        client.ehlo()
        if smtp_config.use_tls:
            context = ssl.create_default_context()
            client.starttls(context=context)
            client.ehlo()
        if smtp_config.username:
            client.login(smtp_config.username, password)
        client.send_message(msg)


def send_materials_task_email(
    *,
    task_id: UUID | str,
    workspace_id: str,
    smtp_config_id: UUID | str,
    email_template_id: UUID | str,
    to_addresses: list[str],
    cc_addresses: list[str] | None = None,
    extra_context: dict[str, Any] | None = None,
    attach_zip: bool = True,
    sent_by: UUID | str,
    request_snapshot: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str = '',
) -> dict[str, Any]:
    """
    Send the materials zip for `task_id` to `to_addresses`.

    Always returns a dict; never raises. Fields:
        status: 'sent' | 'failed'
        log_id: str  (the EmailSendLog row id, always present)
        error: str | None
        task_status: str  (final MaterialsTask.status, success or unchanged)
    """
    to_addresses = list(to_addresses or [])
    cc_addresses = list(cc_addresses or [])

    # ---- Pre-write log row so even catastrophic failures leave a trace --
    log = EmailSendLog.objects.create(
        workspace_id=workspace_id,
        target_type='MATERIALS_TASK',
        target_id=task_id,
        smtp_config_id=smtp_config_id,
        email_template_id=email_template_id,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        subject='',
        body_preview='',
        attachment_keys=[],
        status=EmailSendStatus.QUEUED,
        sent_by=sent_by,
    )

    def _finalize(
        *,
        status: str,
        error: str = '',
        subject_rendered: str = '',
        body_preview: str = '',
        attachment_keys: list[str] | None = None,
        task_status: str | None = None,
    ) -> dict[str, Any]:
        log.status = status
        log.error_message = error
        if subject_rendered:
            log.subject = subject_rendered[:512]
        if body_preview:
            log.body_preview = body_preview[:500]
        if attachment_keys:
            log.attachment_keys = attachment_keys
        if status == EmailSendStatus.SENT:
            log.sent_at = timezone.now()
        log.save()

        # Always audit the send attempt — pass through whatever request
        # snapshot the view captured so the audit row is consistent with
        # other finance writes.
        log_event(
            workspace_id=workspace_id,
            actor_id=sent_by,
            target_type=FinanceAuditTargetType.MATERIALS_TASK,
            target_id=str(task_id),
            action=FinanceAuditAction.SEND,
            payload={
                'log_id': str(log.id),
                'status': status,
                'to_addresses': to_addresses,
                'cc_addresses': cc_addresses,
                'subject': log.subject,
                'error': error or None,
                **(request_snapshot or {}),
            },
            ip=ip,
            user_agent=user_agent,
        )
        return {
            'status': 'sent' if status == EmailSendStatus.SENT else 'failed',
            'log_id': str(log.id),
            'error': error or None,
            'task_status': task_status,
        }

    try:
        # ---- Load supporting rows ----
        task = MaterialsTask.objects.filter(
            id=task_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if task is None:
            return _finalize(
                status=EmailSendStatus.FAILED,
                error='materials task not found',
            )

        smtp_config = SmtpConfig.objects.filter(
            id=smtp_config_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if smtp_config is None:
            return _finalize(
                status=EmailSendStatus.FAILED, error='smtp config not found',
                task_status=task.status,
            )

        template = EmailTemplate.objects.filter(
            id=email_template_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if template is None:
            return _finalize(
                status=EmailSendStatus.FAILED, error='email template not found',
                task_status=task.status,
            )

        if not to_addresses:
            return _finalize(
                status=EmailSendStatus.FAILED, error='no recipients',
                task_status=task.status,
            )

        project = FinanceProject.objects.filter(
            id=task.project_id, workspace_id=workspace_id, is_deleted=False
        ).first()

        # ---- Render template ----
        zip_filename = f'materials-{task.id}.zip'
        context = _build_context(
            task=task,
            project=project,
            to_addresses=to_addresses,
            zip_filename=zip_filename,
            extra_context=extra_context,
        )
        subject = render_template_string(template.subject, context)
        body_text = render_template_string(template.body_text, context)
        body_html = render_template_string(template.body_html, context)

        # ---- Resolve attachment ----
        zip_bytes: bytes | None = None
        attachment_keys: list[str] = []
        if attach_zip:
            if not task.zip_oss_key:
                return _finalize(
                    status=EmailSendStatus.FAILED,
                    error='task has not been packed (no zip_oss_key)',
                    subject_rendered=subject,
                    body_preview=body_text,
                    task_status=task.status,
                )
            try:
                zip_bytes = _load_bytes(task.zip_oss_key)
            except Exception as e:  # noqa: BLE001
                return _finalize(
                    status=EmailSendStatus.FAILED,
                    error=f'failed to load zip: {e!r}',
                    subject_rendered=subject,
                    body_preview=body_text,
                    task_status=task.status,
                )
            if zip_bytes is not None and len(zip_bytes) > _MAX_ATTACHMENT_BYTES:
                return _finalize(
                    status=EmailSendStatus.FAILED,
                    error=(
                        f'attachment too large ({len(zip_bytes)} bytes); '
                        f'limit is {_MAX_ATTACHMENT_BYTES} bytes — use download link'
                    ),
                    subject_rendered=subject,
                    body_preview=body_text,
                    task_status=task.status,
                )
            attachment_keys = [task.zip_oss_key]

        # ---- Build MIME ----
        try:
            msg = _build_email(
                smtp_config=smtp_config,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                zip_bytes=zip_bytes,
                zip_filename=zip_filename,
            )
        except Exception as e:  # noqa: BLE001
            return _finalize(
                status=EmailSendStatus.FAILED,
                error=f'failed to build email: {e!r}',
                subject_rendered=subject,
                body_preview=body_text,
                attachment_keys=attachment_keys,
                task_status=task.status,
            )

        # ---- Mark sending and dial SMTP ----
        log.status = EmailSendStatus.SENDING
        log.subject = subject[:512]
        log.body_preview = (body_text or '')[:500]
        log.attachment_keys = attachment_keys
        log.save(
            update_fields=[
                'status', 'subject', 'body_preview', 'attachment_keys',
            ]
        )

        try:
            _dial_and_send(smtp_config, msg)
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning(
                '[finance.email] SMTP send failed for task=%s: %r', task_id, e
            )
            return _finalize(
                status=EmailSendStatus.FAILED,
                error=f'SMTP send failed: {e!r}',
                subject_rendered=subject,
                body_preview=body_text,
                attachment_keys=attachment_keys,
                task_status=task.status,
            )

        # ---- Success: flip task status ----
        task.status = MaterialsTaskStatus.SENT
        task.save(update_fields=['status', 'updated_at'])

        return _finalize(
            status=EmailSendStatus.SENT,
            subject_rendered=subject,
            body_preview=body_text,
            attachment_keys=attachment_keys,
            task_status=MaterialsTaskStatus.SENT,
        )
    except Exception as e:  # noqa: BLE001 — last-resort guard, never raise
        _LOGGER.exception(
            '[finance.email] unexpected failure sending task=%s', task_id
        )
        return _finalize(
            status=EmailSendStatus.FAILED,
            error=f'unexpected error: {e!r}',
        )


# --------------------------------------------------------------------------
# Test helper — used by SmtpConfigTestView. Does NOT touch MaterialsTask or
# EmailSendLog; only sanity-checks the SMTP credential.
# --------------------------------------------------------------------------


def send_test_email(
    *,
    smtp_config: SmtpConfig,
    to_address: str,
) -> dict[str, Any]:
    """
    Send a small probe email through `smtp_config`. Returns
    `{'success': bool, 'error': str | None}`. Never raises.
    """
    if not to_address:
        return {'success': False, 'error': 'no recipient'}
    try:
        msg = EmailMessage()
        msg['From'] = formataddr(
            (smtp_config.from_name or '', smtp_config.from_email)
        )
        msg['To'] = to_address
        msg['Subject'] = '[MaxKB Finance] SMTP test'
        msg.set_content(
            'This is a test message from the MaxKB Finance workspace.\n'
            f'Sent at {timezone.now().isoformat()}.\n'
        )
        _dial_and_send(smtp_config, msg)
        return {'success': True, 'error': None}
    except Exception as e:  # noqa: BLE001
        _LOGGER.warning('[finance.email] test send failed: %r', e)
        return {'success': False, 'error': repr(e)}



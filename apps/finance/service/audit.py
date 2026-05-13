# coding=utf-8
"""
    @project: MaxKB
    @file： audit.py
    @desc: Audit-log decorator and helper for the finance module.

    The decorator captures actor / workspace / target / IP / UA AFTER the
    wrapped DRF view method returns successfully. Failures (exceptions)
    are not audited here — they propagate to the global exception handler.

    Logging itself is best-effort: any failure inserting the audit row is
    swallowed and surfaced through the project logger, so a broken audit
    pipeline never blocks a user request.
"""
from functools import wraps
from typing import Any, Mapping, Optional

from common.utils.logger import maxkb_logger

# Field names we never want to land in an audit-log payload.
_REDACTED_KEYS = {'password', 'token', 'secret', 'authorization', 'access_token', 'refresh_token'}
_REDACTED_PLACEHOLDER = '***'


def _redact(data: Any) -> Any:
    """
    Recursively redact sensitive fields from request bodies / query params.

    Walks dicts and lists; leaves primitives untouched. Drops the values of
    any key whose lowercased name is in _REDACTED_KEYS.
    """
    if isinstance(data, Mapping):
        return {
            k: (_REDACTED_PLACEHOLDER if str(k).lower() in _REDACTED_KEYS else _redact(v))
            for k, v in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [_redact(item) for item in data]
    return data


def _get_ip(request) -> Optional[str]:
    fwd = request.META.get('HTTP_X_FORWARDED_FOR') if request is not None else None
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') if request is not None else None


def _get_ua(request) -> str:
    if request is None:
        return ''
    return (request.META.get('HTTP_USER_AGENT') or '')[:512]


def _get_actor_id(request):
    user = getattr(request, 'user', None) if request is not None else None
    user_id = getattr(user, 'id', None) if user is not None else None
    return user_id


def _extract_target_id(kwargs: dict, response) -> Optional[str]:
    """
    Prefer URL kwargs (detail/update/delete routes), fall back to the response
    body's id (create route returns the new row's id).
    """
    pk = kwargs.get('pk') or kwargs.get('id')
    if pk:
        return str(pk)
    try:
        # response is typically a result.Result (JsonResponse subclass).
        data = getattr(response, 'data', None)
        if data is None:
            return None
        envelope = data.get('data') if isinstance(data, Mapping) else None
        if isinstance(envelope, Mapping):
            inner = envelope.get('id')
            if inner:
                return str(inner)
    except Exception:  # noqa: BLE001 — best effort
        return None
    return None


def _safe_request_snapshot(request) -> dict:
    """
    Best-effort, redacted snapshot of the inbound request. Always returns a
    dict; never raises.
    """
    if request is None:
        return {}
    try:
        body = getattr(request, 'data', None)
        body = body if isinstance(body, Mapping) else {}
    except Exception:  # noqa: BLE001
        body = {}
    try:
        params = dict(request.query_params) if hasattr(request, 'query_params') else {}
    except Exception:  # noqa: BLE001
        params = {}
    return {
        'path': getattr(request, 'path', ''),
        'method': getattr(request, 'method', ''),
        'body': _redact(body),
        'query': _redact(params),
    }


def log_event(
    *,
    workspace_id,
    actor_id,
    target_type: str,
    action: str,
    target_id=None,
    payload: Optional[dict] = None,
    ip: Optional[str] = None,
    user_agent: str = '',
) -> None:
    """
    Programmatic helper for code paths the decorator can't reach
    (e.g. Celery tasks, background jobs).

    Silently swallows ORM failures — audit logging must never break the
    calling code path. We log the exception via maxkb_logger instead.
    """
    # Local import: avoids a circular import at module-load time when this
    # service module is imported during Django app initialization.
    from finance.models import FinanceAuditLog

    try:
        FinanceAuditLog.objects.create(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            action=action,
            payload=payload or {},
            ip=ip,
            user_agent=(user_agent or '')[:512],
        )
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(f'[finance.audit] failed to write audit log: {e}', exc_info=True)


def audit_log(action: str, target_type: str):
    """
    Decorator for DRF APIView methods of the shape
        def method(self, request, *args, **kwargs): ...

    On success: writes a FinanceAuditLog row with actor/workspace/target/IP/UA
    plus a redacted snapshot of the request.
    On failure: does NOT write a log; the exception propagates unchanged.
    """

    def outer(func):
        @wraps(func)
        def inner(self, request, *args, **kwargs):
            response = func(self, request, *args, **kwargs)
            try:
                workspace_id = kwargs.get('workspace_id')
                actor_id = _get_actor_id(request)
                target_id = _extract_target_id(kwargs, response)
                log_event(
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    target_type=target_type,
                    target_id=target_id,
                    action=action,
                    payload=_safe_request_snapshot(request),
                    ip=_get_ip(request),
                    user_agent=_get_ua(request),
                )
            except Exception as e:  # noqa: BLE001 — never break the request
                maxkb_logger.error(f'[finance.audit] decorator failed: {e}', exc_info=True)
            return response

        return inner

    return outer

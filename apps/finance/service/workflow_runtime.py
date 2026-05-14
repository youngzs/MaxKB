# coding=utf-8
"""
    @project: MaxKB
    @file:   workflow_runtime.py
    @desc:   Shared helpers for the Gate 7 Track B Celery wrappers.

    A WorkflowRun row is created by the task itself at start (status=RUNNING)
    and updated at end (SUCCEEDED / FAILED). The async dispatch layer in the
    views creates a QUEUED row first so the UI can observe the pending work
    even before the worker picks it up. The task then promotes its dedicated
    row to RUNNING when execution begins.

    Error taxonomy used by callers:
      - TransientError: re-raised so Celery retries the task. Symptom of a
        flaky dependency (DB connection, OSS, network); the underlying work
        is expected to succeed on a fresh attempt.
      - BusinessError: caught, logged into error_message, status=FAILED;
        NOT retried. Symptom of a real defect (template missing, file
        corrupt, LLM rejected the input). Retrying would just repeat the
        same outcome.
"""
from __future__ import annotations

import time
from typing import Optional

from django.utils import timezone

from common.utils.logger import maxkb_logger
from finance.models import WorkflowRun, WorkflowRunStatus


# ---------- error sentinel classes ---------------------------------------


class BusinessError(Exception):
    """Permanent failure — do NOT retry."""


class TransientError(Exception):
    """Recoverable failure — Celery should retry."""


# ---------- DB-error classification --------------------------------------
#
# We treat the following as transient: connection drops, deadlocks, lock-not-
# available timeouts. Everything else from the DB driver (IntegrityError,
# ProgrammingError, DataError) is treated as a permanent business error.


def is_transient_exception(exc: BaseException) -> bool:
    """
    Best-effort classifier. Returns True for exceptions that are typically
    fixed by waiting and retrying:
      - django.db.OperationalError (lost connection, lock timeout)
      - django.db.InterfaceError (connection already closed)
      - redis / kombu / requests connection errors
      - explicit TransientError sentinels
    Otherwise returns False so the caller treats it as a business failure.
    """
    if isinstance(exc, TransientError):
        return True
    if isinstance(exc, BusinessError):
        return False
    # Lazy imports — these are only used as type-check material.
    try:
        from django.db import InterfaceError, OperationalError
        if isinstance(exc, (OperationalError, InterfaceError)):
            return True
    except Exception:  # noqa: BLE001
        pass
    name = type(exc).__name__.lower()
    # Common transient patterns from outside the Django ORM.
    transient_markers = (
        'connectionerror',
        'connectionreset',
        'timeout',
        'temporaryfailure',
        'remotedisconnected',
    )
    return any(marker in name for marker in transient_markers)


# ---------- WorkflowRun helpers ------------------------------------------


def create_queued_run(
    *,
    workspace_id: str,
    target_type: str,
    target_id,
    task_name: str,
    payload: Optional[dict] = None,
) -> Optional[WorkflowRun]:
    """
    Create a QUEUED WorkflowRun row at dispatch time. Returns the row, or
    None if persistence failed (we never block the dispatch path on audit
    state). Caller is responsible for passing the resulting `id` into the
    Celery task so the worker can promote it to RUNNING.
    """
    try:
        return WorkflowRun.objects.create(
            workspace_id=str(workspace_id) if workspace_id is not None else '',
            target_type=target_type,
            target_id=str(target_id),
            task_name=task_name,
            status=WorkflowRunStatus.QUEUED,
            payload=payload or {},
        )
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_runtime] create_queued_run failed: {e}',
            exc_info=True,
        )
        return None


def mark_running(
    run_id, *, celery_task_id: str = ''
) -> tuple[Optional[WorkflowRun], float]:
    """
    Promote a QUEUED row to RUNNING and record `started_at`. Returns
    (row, monotonic_start_time) — the second value is the basis for
    computing `duration_ms` later. If the row no longer exists or the
    update fails, returns (None, now()) so the caller can still proceed.
    """
    start = time.monotonic()
    if run_id is None:
        return None, start
    try:
        run = WorkflowRun.objects.filter(id=run_id).first()
        if run is None:
            return None, start
        run.status = WorkflowRunStatus.RUNNING
        run.started_at = timezone.now()
        if celery_task_id:
            run.celery_task_id = celery_task_id[:64]
        run.save(
            update_fields=['status', 'started_at', 'celery_task_id', 'updated_at']
        )
        return run, start
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_runtime] mark_running failed: {e}', exc_info=True
        )
        return None, start


def mark_succeeded(
    run: Optional[WorkflowRun], start: float, *, output: Optional[dict] = None
) -> None:
    if run is None:
        return
    try:
        run.status = WorkflowRunStatus.SUCCEEDED
        run.finished_at = timezone.now()
        run.duration_ms = int(max(0, (time.monotonic() - start) * 1000))
        run.error_message = ''
        if output is not None:
            merged = dict(run.payload or {})
            merged['output'] = output
            run.payload = merged
        run.save(
            update_fields=[
                'status', 'finished_at', 'duration_ms',
                'error_message', 'payload', 'updated_at',
            ]
        )
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_runtime] mark_succeeded failed: {e}', exc_info=True
        )


def mark_failed(
    run: Optional[WorkflowRun],
    start: float,
    *,
    error_message: str,
    retry_count: Optional[int] = None,
) -> None:
    if run is None:
        return
    try:
        run.status = WorkflowRunStatus.FAILED
        run.finished_at = timezone.now()
        run.duration_ms = int(max(0, (time.monotonic() - start) * 1000))
        run.error_message = (error_message or '')[:8000]
        if retry_count is not None:
            run.retry_count = retry_count
        run.save(
            update_fields=[
                'status', 'finished_at', 'duration_ms',
                'error_message', 'retry_count', 'updated_at',
            ]
        )
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_runtime] mark_failed failed: {e}', exc_info=True
        )


def mark_retrying(
    run: Optional[WorkflowRun],
    start: float,
    *,
    error_message: str,
    retry_count: int,
) -> None:
    if run is None:
        return
    try:
        run.status = WorkflowRunStatus.RETRYING
        run.duration_ms = int(max(0, (time.monotonic() - start) * 1000))
        run.error_message = (error_message or '')[:8000]
        run.retry_count = retry_count
        run.save(
            update_fields=[
                'status', 'duration_ms', 'error_message',
                'retry_count', 'updated_at',
            ]
        )
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_runtime] mark_retrying failed: {e}',
            exc_info=True,
        )

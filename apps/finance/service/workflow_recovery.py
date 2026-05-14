# coding=utf-8
"""
    @project: MaxKB
    @file:   workflow_recovery.py
    @desc:   Stuck-task detection + recovery helpers (Gate 8 Track B).

    Gate 7 added the async Celery pipeline with a WorkflowRun row per
    invocation. In production a worker can die mid-task, the broker can
    lose a message, or a task can wedge — leaving a WorkflowRun stuck in
    'queued' / 'running' forever and the underlying MaterialsTask /
    DocumentGeneration stuck in its in-flight state.

    This module provides:
      - find_stale_runs(): read-only — surfaces candidates for the UI's
        "可能已卡住" badge and for the cleanup command's dry-run.
      - auto_fail_stale_runs(): write — marks genuinely-stale runs FAILED
        and fails the underlying target. Intended to be driven by the
        cleanup_stale_workflow_runs management command (ops crons it).
        It is deliberately NOT auto-scheduled here.

    Everything is defensive: a recovery helper that itself raises would
    make the problem worse, so DB failures are logged and swallowed.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from django.utils import timezone

from common.utils.logger import maxkb_logger
from finance.models import WorkflowRun, WorkflowRunStatus

# Statuses that represent "work that should be progressing". A row sitting
# in one of these long after it started is the definition of stuck.
_IN_FLIGHT_STATUSES = (
    WorkflowRunStatus.QUEUED,
    WorkflowRunStatus.RUNNING,
    WorkflowRunStatus.RETRYING,
)

# Sentinel error message written onto auto-failed runs / targets so an
# operator triaging later can tell apart "the task itself failed" from
# "the worker vanished and we reaped it".
_STALE_ERROR = 'timed out / worker lost'
_STALE_TARGET_ERROR = 'Workflow run timed out / worker lost'


def _cutoff(stale_after_minutes: int):
    """Return the timezone-aware datetime before which a run counts stale."""
    minutes = stale_after_minutes if stale_after_minutes and stale_after_minutes > 0 else 15
    return timezone.now() - timedelta(minutes=minutes)


def _run_to_dict(row: WorkflowRun) -> dict:
    """Compact dict mirroring the workflow_run list serializer shape."""
    return {
        'id': str(row.id),
        'workspace_id': row.workspace_id,
        'target_type': row.target_type,
        'target_id': str(row.target_id),
        'task_name': row.task_name,
        'celery_task_id': row.celery_task_id,
        'status': row.status,
        'started_at': row.started_at.isoformat() if row.started_at else None,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'retry_count': row.retry_count,
    }


def find_stale_runs(workspace_id: str, stale_after_minutes: int = 15) -> list:
    """
    WorkflowRun rows stuck in 'running'/'queued'/'retrying' whose work
    began (``started_at`` when present, else ``created_at`` for rows the
    worker never picked up) older than ``stale_after_minutes``.

    Read-only — these are candidates for auto-fail or manual retry. The
    caller decides what to do; this function never mutates anything.
    Returns a list of compact dicts ordered oldest-first.
    """
    try:
        cutoff = _cutoff(stale_after_minutes)
        # A row is stale if it started before the cutoff, OR it never
        # started at all (still QUEUED) and was created before the cutoff.
        from django.db.models import Q

        qs = (
            WorkflowRun.objects
            .filter(workspace_id=str(workspace_id))
            .filter(status__in=list(_IN_FLIGHT_STATUSES))
            .filter(
                Q(started_at__lt=cutoff)
                | Q(started_at__isnull=True, created_at__lt=cutoff)
            )
            .order_by('created_at')
        )
        return [_run_to_dict(r) for r in qs]
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_recovery] find_stale_runs failed: {exc}',
            exc_info=True,
        )
        return []


def _fail_underlying_target(row: WorkflowRun) -> None:
    """
    Best-effort: drag the MaterialsTask / DocumentGeneration that this run
    belongs to into its FAILED state so the UI stops showing a spinner.
    Never raises — a failure here is logged and swallowed.
    """
    try:
        target_type = (row.target_type or '').upper()
        if target_type == 'MATERIALS_TASK':
            from finance.models import MaterialsTask, MaterialsTaskStatus

            task = MaterialsTask.objects.filter(id=row.target_id).first()
            if task is not None and task.status not in (
                MaterialsTaskStatus.FAILED,
                MaterialsTaskStatus.SENT,
                MaterialsTaskStatus.APPROVED,
                MaterialsTaskStatus.REJECTED,
            ):
                task.status = MaterialsTaskStatus.FAILED
                task.error_message = _STALE_TARGET_ERROR
                task.save(update_fields=['status', 'error_message', 'updated_at'])
        elif target_type == 'DOC_GENERATION':
            from finance.models import DocumentGeneration, GenerationStatus

            gen = DocumentGeneration.objects.filter(id=row.target_id).first()
            if gen is not None and gen.status == GenerationStatus.GENERATING:
                gen.status = GenerationStatus.FAILED
                gen.error_message = _STALE_TARGET_ERROR
                gen.save(update_fields=['status', 'error_message', 'updated_at'])
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_recovery] _fail_underlying_target '
            f'({row.target_type}/{row.target_id}) failed: {exc}',
            exc_info=True,
        )


def auto_fail_stale_runs(stale_after_minutes: int = 30) -> int:
    """
    Mark genuinely-stale runs (older than ``stale_after_minutes``, default
    30) as 'failed' with error='timed out / worker lost'. Also fails the
    underlying MaterialsTask / DocumentGeneration.

    Returns the count of runs failed.

    Intended to be called from a periodic task or the
    ``cleanup_stale_workflow_runs`` management command — this function
    does NOT auto-run anywhere; ops decides the cadence.
    """
    failed = 0
    try:
        cutoff = _cutoff(stale_after_minutes if stale_after_minutes else 30)
        from django.db.models import Q

        qs = (
            WorkflowRun.objects
            .filter(status__in=list(_IN_FLIGHT_STATUSES))
            .filter(
                Q(started_at__lt=cutoff)
                | Q(started_at__isnull=True, created_at__lt=cutoff)
            )
            .order_by('created_at')
        )
        for row in qs:
            try:
                row.status = WorkflowRunStatus.FAILED
                row.finished_at = timezone.now()
                row.error_message = _STALE_ERROR
                row.save(
                    update_fields=[
                        'status', 'finished_at', 'error_message', 'updated_at',
                    ]
                )
                _fail_underlying_target(row)
                failed += 1
            except Exception as exc:  # noqa: BLE001
                maxkb_logger.error(
                    f'[finance.workflow_recovery] auto_fail_stale_runs row '
                    f'{row.id} failed: {exc}',
                    exc_info=True,
                )
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_recovery] auto_fail_stale_runs failed: {exc}',
            exc_info=True,
        )
    return failed


def is_run_stale(
    status: str,
    started_at: Optional[Any],
    created_at: Optional[Any],
    stale_after_minutes: int = 15,
) -> bool:
    """
    Pure predicate — True if a single run (described by its status +
    timestamps) counts as stale. Used by the retry/cancel views to avoid
    re-querying; the frontend computes the same thing client-side.
    """
    if status not in (s.value for s in _IN_FLIGHT_STATUSES):
        return False
    cutoff = _cutoff(stale_after_minutes)
    anchor = started_at or created_at
    if anchor is None:
        return False
    try:
        return anchor < cutoff
    except TypeError:
        return False

# coding=utf-8
"""
    @project: MaxKB
    @file:   materials.py
    @desc:   Async (Celery) wrappers around the MaterialsTask state-machine
             steps that were previously called inline from the DRF views.

    Each task:
      1. Loads the MaterialsTask row by id and the WorkflowRun row (if any).
      2. Promotes the run to RUNNING and records a monotonic start time.
      3. Sets the task's `status` field to a transient state (parsing/
         matching) so the UI poll picks up "work in flight" immediately.
      4. Calls the existing synchronous service function — this is the
         load-bearing line; we deliberately do not reimplement business
         logic here.
      5. On success: status → next stable state, WorkflowRun SUCCEEDED,
         audit log row written.
      6. On *transient* failure: WorkflowRun RETRYING, Celery re-raises so
         the broker can re-queue (up to ``max_retries`` configured below).
      7. On *business* failure: status → FAILED with error_message, audit
         log row written, no retry.
"""
from __future__ import annotations

import traceback
from typing import Optional

from common.utils.logger import maxkb_logger
from ops import celery_app


# ---- safety: keep these short so they survive logger truncation ---------
_NAME_PARSE = 'finance.materials.async_parse'
_NAME_MATCH = 'finance.materials.async_match'
_NAME_PACK = 'finance.materials.async_pack'


def _audit(target_id, action: str, payload: dict, workspace_id, actor_id):
    """Log a finance audit row from inside a Celery worker."""
    try:
        from finance.service.audit import log_event
        log_event(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_type='MATERIALS_TASK',
            target_id=target_id,
            action=action,
            payload=payload or {},
        )
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(f'[finance.tasks.materials] audit failed: {e}', exc_info=True)


def _load_task(task_id):
    """Resolve the row or return None — never raise."""
    try:
        from finance.models import MaterialsTask
        return MaterialsTask.objects.filter(id=task_id, is_deleted=False).first()
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.tasks.materials] _load_task({task_id}) failed: {e}',
            exc_info=True,
        )
        return None


def _set_status(instance, status, *, error_message: Optional[str] = None):
    """Persist a status change with a single targeted UPDATE."""
    try:
        instance.status = status
        if error_message is not None:
            instance.error_message = (error_message or '')[:8000]
            instance.save(update_fields=['status', 'error_message', 'updated_at'])
        else:
            instance.save(update_fields=['status', 'updated_at'])
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.tasks.materials] _set_status failed: {e}', exc_info=True
        )


# ===========================================================================
# async_parse
# ===========================================================================


@celery_app.task(name=_NAME_PARSE, bind=True, max_retries=2, default_retry_delay=10)
def async_parse(self, materials_task_id, run_id=None):
    """Parse `requirement_text` (or the uploaded file) into structured items."""
    from finance.models import MaterialsTaskStatus
    from finance.service import workflow_runtime
    from finance.views.materials_task import _do_parse

    run, t0 = workflow_runtime.mark_running(
        run_id, celery_task_id=getattr(self.request, 'id', '') or ''
    )
    instance = _load_task(materials_task_id)
    if instance is None:
        workflow_runtime.mark_failed(
            run, t0, error_message=f'MaterialsTask {materials_task_id} not found'
        )
        return

    workspace_id = instance.workspace_id
    actor_id = instance.created_by

    _set_status(instance, MaterialsTaskStatus.PARSING, error_message='')
    try:
        instance = _do_parse(instance, workspace_id=workspace_id)
        workflow_runtime.mark_succeeded(
            run, t0, output={'parsed_items_count': len(instance.parsed_items or [])}
        )
        _audit(
            target_id=str(instance.id),
            action='UPDATE',
            payload={'event': 'PARSE_COMPLETE', 'count': len(instance.parsed_items or [])},
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
    except Exception as e:  # noqa: BLE001
        msg = repr(e)
        maxkb_logger.error(
            f'[finance.tasks.async_parse] {materials_task_id} failed: {msg}\n'
            f'{traceback.format_exc()}'
        )
        if workflow_runtime.is_transient_exception(e) and self.request.retries < self.max_retries:
            workflow_runtime.mark_retrying(
                run, t0, error_message=msg, retry_count=self.request.retries + 1
            )
            raise self.retry(exc=e)
        # Business failure (or retries exhausted) — write FAILED and stop.
        fresh = _load_task(materials_task_id)
        if fresh is not None:
            _set_status(fresh, MaterialsTaskStatus.FAILED, error_message=msg)
        workflow_runtime.mark_failed(
            run, t0, error_message=msg, retry_count=self.request.retries
        )
        _audit(
            target_id=str(materials_task_id),
            action='UPDATE',
            payload={'event': 'PARSE_FAILED', 'error': msg[:512]},
            workspace_id=workspace_id,
            actor_id=actor_id,
        )


# ===========================================================================
# async_match
# ===========================================================================


@celery_app.task(name=_NAME_MATCH, bind=True, max_retries=2, default_retry_delay=10)
def async_match(self, materials_task_id, user_max_sensitivity=None, run_id=None):
    """
    Sensitivity-aware knowledge match for each parsed item.

    `user_max_sensitivity` is captured at dispatch time on the request
    thread so the worker honours the dispatcher's permissions rather than
    re-deriving from a fake celery context. Falls back to the lowest tier
    ('public') if None — fail-safe, never over-exposes.
    """
    from common.constants.sensitivity_constants import SensitivityLevel
    from finance.models import MaterialsTaskStatus
    from finance.service import workflow_runtime
    from finance.views.materials_task import _do_match

    run, t0 = workflow_runtime.mark_running(
        run_id, celery_task_id=getattr(self.request, 'id', '') or ''
    )
    instance = _load_task(materials_task_id)
    if instance is None:
        workflow_runtime.mark_failed(
            run, t0, error_message=f'MaterialsTask {materials_task_id} not found'
        )
        return

    workspace_id = instance.workspace_id
    actor_id = instance.created_by

    _set_status(instance, MaterialsTaskStatus.MATCHING, error_message='')
    try:
        instance = _do_match(
            instance,
            workspace_id=workspace_id,
            user_max_sensitivity=user_max_sensitivity
            or SensitivityLevel.PUBLIC.value,
        )
        # Match leaves status as DRAFT (matched_documents populated). The
        # MATCHING flag was a transient marker for the poller.
        _set_status(instance, MaterialsTaskStatus.DRAFT)
        workflow_runtime.mark_succeeded(
            run, t0, output={'matched_count': len(instance.matched_documents or [])}
        )
        _audit(
            target_id=str(instance.id),
            action='UPDATE',
            payload={'event': 'MATCH_COMPLETE', 'count': len(instance.matched_documents or [])},
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
    except Exception as e:  # noqa: BLE001
        msg = repr(e)
        maxkb_logger.error(
            f'[finance.tasks.async_match] {materials_task_id} failed: {msg}\n'
            f'{traceback.format_exc()}'
        )
        if workflow_runtime.is_transient_exception(e) and self.request.retries < self.max_retries:
            workflow_runtime.mark_retrying(
                run, t0, error_message=msg, retry_count=self.request.retries + 1
            )
            raise self.retry(exc=e)
        fresh = _load_task(materials_task_id)
        if fresh is not None:
            _set_status(fresh, MaterialsTaskStatus.FAILED, error_message=msg)
        workflow_runtime.mark_failed(
            run, t0, error_message=msg, retry_count=self.request.retries
        )
        _audit(
            target_id=str(materials_task_id),
            action='UPDATE',
            payload={'event': 'MATCH_FAILED', 'error': msg[:512]},
            workspace_id=workspace_id,
            actor_id=actor_id,
        )


# ===========================================================================
# async_pack
# ===========================================================================


@celery_app.task(name=_NAME_PACK, bind=True, max_retries=1, default_retry_delay=30)
def async_pack(self, materials_task_id, item_groups=None, run_id=None):
    """Zip up the selected documents. Sets status=APPROVED on success."""
    from finance.models import MaterialsTaskStatus
    from finance.service import workflow_runtime
    from finance.views.materials_task import _do_pack

    run, t0 = workflow_runtime.mark_running(
        run_id, celery_task_id=getattr(self.request, 'id', '') or ''
    )
    instance = _load_task(materials_task_id)
    if instance is None:
        workflow_runtime.mark_failed(
            run, t0, error_message=f'MaterialsTask {materials_task_id} not found'
        )
        return

    workspace_id = instance.workspace_id
    actor_id = instance.created_by

    # Reuse MATCHING as the in-flight indicator for pack — the UI already
    # treats it as a transient state and shows a spinner. APPROVED is the
    # success state.
    _set_status(instance, MaterialsTaskStatus.MATCHING, error_message='')
    try:
        instance = _do_pack(
            instance, workspace_id=workspace_id, override_groups=item_groups
        )
        workflow_runtime.mark_succeeded(
            run, t0, output={'zip_oss_key': instance.zip_oss_key}
        )
        _audit(
            target_id=str(instance.id),
            action='UPDATE',
            payload={'event': 'PACK_COMPLETE', 'zip_oss_key': instance.zip_oss_key},
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
    except Exception as e:  # noqa: BLE001
        msg = repr(e)
        maxkb_logger.error(
            f'[finance.tasks.async_pack] {materials_task_id} failed: {msg}\n'
            f'{traceback.format_exc()}'
        )
        if workflow_runtime.is_transient_exception(e) and self.request.retries < self.max_retries:
            workflow_runtime.mark_retrying(
                run, t0, error_message=msg, retry_count=self.request.retries + 1
            )
            raise self.retry(exc=e)
        fresh = _load_task(materials_task_id)
        if fresh is not None:
            _set_status(fresh, MaterialsTaskStatus.FAILED, error_message=msg)
        workflow_runtime.mark_failed(
            run, t0, error_message=msg, retry_count=self.request.retries
        )
        _audit(
            target_id=str(materials_task_id),
            action='UPDATE',
            payload={'event': 'PACK_FAILED', 'error': msg[:512]},
            workspace_id=workspace_id,
            actor_id=actor_id,
        )

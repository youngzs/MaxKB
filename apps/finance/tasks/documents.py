# coding=utf-8
"""
    @project: MaxKB
    @file:   documents.py
    @desc:   Async wrapper for DocumentGeneration rendering.

    trigger_generation is already self-contained — it loads the row, never
    raises, and writes the FAILED state itself on render error. The task
    here therefore stays very thin: lifecycle bookkeeping for WorkflowRun
    plus an audit entry; the heavy lifting stays in document_generator.
"""
from __future__ import annotations

import traceback

from common.utils.logger import maxkb_logger
from ops import celery_app


_NAME_GENERATE = 'finance.documents.async_generate'


def _audit(target_id, action: str, payload: dict, workspace_id, actor_id):
    try:
        from finance.service.audit import log_event
        log_event(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_type='DOC_GENERATION',
            target_id=target_id,
            action=action,
            payload=payload or {},
        )
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.tasks.documents] audit failed: {e}', exc_info=True
        )


@celery_app.task(name=_NAME_GENERATE, bind=True, max_retries=2, default_retry_delay=10)
def async_generate(self, generation_id, run_id=None):
    """Render a DocumentGeneration row in the background."""
    from finance.models import DocumentGeneration, GenerationStatus
    from finance.service import workflow_runtime
    from finance.service.document_generator import trigger_generation

    run, t0 = workflow_runtime.mark_running(
        run_id, celery_task_id=getattr(self.request, 'id', '') or ''
    )

    try:
        gen = DocumentGeneration.objects.filter(id=generation_id).first()
    except Exception as e:  # noqa: BLE001
        # DB read failure — classify as transient if it looks like one.
        if workflow_runtime.is_transient_exception(e) and self.request.retries < self.max_retries:
            workflow_runtime.mark_retrying(
                run, t0, error_message=repr(e), retry_count=self.request.retries + 1
            )
            raise self.retry(exc=e)
        workflow_runtime.mark_failed(
            run, t0, error_message=repr(e), retry_count=self.request.retries
        )
        return

    if gen is None:
        workflow_runtime.mark_failed(
            run, t0, error_message=f'DocumentGeneration {generation_id} not found'
        )
        return

    workspace_id = gen.workspace_id
    actor_id = gen.created_by

    # Pin the dedicated workflow_run_id onto the generation row so the UI
    # can resolve back to this run directly (audit-trail breadcrumb).
    if run is not None and gen.workflow_run_id != run.id:
        try:
            gen.workflow_run_id = run.id
            gen.save(update_fields=['workflow_run_id', 'updated_at'])
        except Exception as e:  # noqa: BLE001
            maxkb_logger.warning(
                f'[finance.tasks.async_generate] could not pin workflow_run_id: {e}'
            )

    try:
        # trigger_generation never raises; it updates `status` and
        # `error_message` itself. We then read them back to decide
        # what to record on the WorkflowRun.
        trigger_generation(gen.id)
        gen.refresh_from_db()
    except Exception as e:  # noqa: BLE001
        # Defensive — shouldn't happen because trigger_generation catches
        # everything, but if it ever does, treat the same as below.
        msg = repr(e)
        maxkb_logger.error(
            f'[finance.tasks.async_generate] {generation_id} blew up: {msg}\n'
            f'{traceback.format_exc()}'
        )
        if workflow_runtime.is_transient_exception(e) and self.request.retries < self.max_retries:
            workflow_runtime.mark_retrying(
                run, t0, error_message=msg, retry_count=self.request.retries + 1
            )
            raise self.retry(exc=e)
        workflow_runtime.mark_failed(
            run, t0, error_message=msg, retry_count=self.request.retries
        )
        _audit(
            target_id=str(generation_id),
            action='UPDATE',
            payload={'event': 'GENERATE_FAILED', 'error': msg[:512]},
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
        return

    if gen.status == GenerationStatus.FAILED:
        workflow_runtime.mark_failed(
            run, t0,
            error_message=gen.error_message or 'generation failed',
            retry_count=self.request.retries,
        )
        _audit(
            target_id=str(gen.id),
            action='UPDATE',
            payload={
                'event': 'GENERATE_FAILED',
                'error': (gen.error_message or '')[:512],
            },
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
    else:
        workflow_runtime.mark_succeeded(
            run, t0, output={'output_oss_key': gen.output_oss_key, 'status': gen.status}
        )
        _audit(
            target_id=str(gen.id),
            action='UPDATE',
            payload={'event': 'GENERATE_COMPLETE', 'status': gen.status},
            workspace_id=workspace_id,
            actor_id=actor_id,
        )

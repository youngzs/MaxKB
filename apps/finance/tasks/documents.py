# coding=utf-8
"""
    @project: MaxKB
    @file:   documents.py
    @desc:   Async wrapper for DocumentGeneration rendering.

    trigger_generation is already self-contained — it loads the row, never
    raises, and writes the FAILED state itself on render error. The task
    here therefore stays very thin: lifecycle bookkeeping for WorkflowRun
    plus an audit entry; the heavy lifting stays in document_generator.

    Gate 8 Track A: when ``FINANCE_USE_WORKFLOW_ENGINE`` is set, the task
    first attempts the ``__internal_document_generator`` preset workflow via
    ``finance.service.workflow_executor.run_workflow``. On any
    ``WorkflowExecutionError`` it falls back to the direct service call. The
    flag defaults OFF — see workflow_executor.py for why the preset workflow
    is not yet reliable. The direct-call path is always the safety net.
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


def _record_run_engine(run, summary: dict):
    """
    Merge the engine/app_id/node_count/io-summary block into
    ``WorkflowRun.payload`` so the audit trail can tell a workflow-engine
    run apart from a direct-service-call run. Never raises.
    """
    if run is None or not summary:
        return
    try:
        merged = dict(run.payload or {})
        merged.update(summary)
        run.payload = merged
        run.save(update_fields=['payload', 'updated_at'])
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.tasks.documents] _record_run_engine failed: {e}',
            exc_info=True,
        )


def _try_workflow_engine(gen):
    """
    Attempt the ``__internal_document_generator`` preset workflow for this
    DocumentGeneration row.

    Returns a dict ``{'engine': 'workflow', 'app_id': ..., 'output': {...}}``
    on success, or ``None`` if the engine is disabled or the run failed
    (caller then falls back to the direct service call). Never raises —
    WorkflowExecutionError is caught and logged here.
    """
    from finance.service.workflow_executor import (
        DOC_GENERATOR_APP_ID,
        WorkflowExecutionError,
        run_workflow,
        summarize_io,
        use_workflow_engine,
    )

    if not use_workflow_engine():
        return None

    inputs = {
        'project_id': str(gen.project_id) if getattr(gen, 'project_id', None) else '',
        'template_id': str(gen.template_id) if gen.template_id else '',
        'placeholder_keys': sorted((gen.placeholder_values or {}).keys()),
        'placeholder_values': gen.placeholder_values or {},
    }
    try:
        output = run_workflow(DOC_GENERATOR_APP_ID, inputs, gen.workspace_id)
    except WorkflowExecutionError as e:
        maxkb_logger.warning(
            f'[finance.tasks.async_generate] workflow engine failed for '
            f'{gen.id}, falling back to direct service: {e}'
        )
        return None
    except Exception as e:  # noqa: BLE001 - never let the engine path crash the task
        maxkb_logger.warning(
            f'[finance.tasks.async_generate] workflow engine raised unexpectedly '
            f'for {gen.id}, falling back to direct service: {e!r}'
        )
        return None

    return {
        'summary': summarize_io(
            engine='workflow', app_id=DOC_GENERATOR_APP_ID,
            inputs=inputs, output=output,
        ),
        'output': output,
    }


@celery_app.task(name=_NAME_GENERATE, bind=True, max_retries=2, default_retry_delay=10)
def async_generate(self, generation_id, run_id=None):
    """Render a DocumentGeneration row in the background."""
    from finance.models import DocumentGeneration, GenerationStatus
    from finance.service import workflow_runtime
    from finance.service.document_generator import trigger_generation
    from finance.service.workflow_executor import summarize_io

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

    # ---- Phase 3: workflow-engine path (gated, best-effort) -------------
    # If the engine path succeeds we map its output back onto the row and
    # skip the direct call entirely. If it returns None we fall through to
    # the direct service call below — that path is the safety net.
    engine_result = _try_workflow_engine(gen)
    if engine_result is not None:
        output = engine_result['output']
        output_oss_key = output.get('output_oss_key') or ''
        wf_err = output.get('error')
        try:
            if output_oss_key and not wf_err:
                gen.output_oss_key = output_oss_key
                gen.status = GenerationStatus.PENDING_REVIEW
                gen.error_message = ''
                gen.save(update_fields=[
                    'output_oss_key', 'status', 'error_message', 'updated_at',
                ])
            else:
                gen.status = GenerationStatus.FAILED
                gen.error_message = (wf_err or 'workflow produced no output')[:8000]
                gen.save(update_fields=['status', 'error_message', 'updated_at'])
        except Exception as e:  # noqa: BLE001
            maxkb_logger.error(
                f'[finance.tasks.async_generate] could not persist workflow '
                f'output for {generation_id}: {e!r}'
            )
            # Fall through to the direct call rather than leaving a half state.
            engine_result = None

    if engine_result is not None:
        if gen.status == GenerationStatus.FAILED:
            workflow_runtime.mark_failed(
                run, t0,
                error_message=gen.error_message or 'workflow generation failed',
                retry_count=self.request.retries,
            )
            _record_run_engine(run, engine_result['summary'])
            _audit(
                target_id=str(gen.id),
                action='UPDATE',
                payload={
                    'event': 'GENERATE_FAILED',
                    'engine': 'workflow',
                    'error': (gen.error_message or '')[:512],
                },
                workspace_id=workspace_id,
                actor_id=actor_id,
            )
        else:
            workflow_runtime.mark_succeeded(
                run, t0,
                output={'output_oss_key': gen.output_oss_key, 'status': gen.status},
            )
            _record_run_engine(run, engine_result['summary'])
            _audit(
                target_id=str(gen.id),
                action='UPDATE',
                payload={
                    'event': 'GENERATE_COMPLETE',
                    'engine': 'workflow',
                    'status': gen.status,
                },
                workspace_id=workspace_id,
                actor_id=actor_id,
            )
        return

    # ---- direct-service-call path (primary / fallback) -----------------
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

    direct_summary = summarize_io(
        engine='direct', app_id=None,
        inputs={'generation_id': str(generation_id)},
        output={'output_oss_key': gen.output_oss_key, 'status': gen.status},
    )

    if gen.status == GenerationStatus.FAILED:
        workflow_runtime.mark_failed(
            run, t0,
            error_message=gen.error_message or 'generation failed',
            retry_count=self.request.retries,
        )
        _record_run_engine(run, direct_summary)
        _audit(
            target_id=str(gen.id),
            action='UPDATE',
            payload={
                'event': 'GENERATE_FAILED',
                'engine': 'direct',
                'error': (gen.error_message or '')[:512],
            },
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
    else:
        workflow_runtime.mark_succeeded(
            run, t0, output={'output_oss_key': gen.output_oss_key, 'status': gen.status}
        )
        _record_run_engine(run, direct_summary)
        _audit(
            target_id=str(gen.id),
            action='UPDATE',
            payload={
                'event': 'GENERATE_COMPLETE',
                'engine': 'direct',
                'status': gen.status,
            },
            workspace_id=workspace_id,
            actor_id=actor_id,
        )

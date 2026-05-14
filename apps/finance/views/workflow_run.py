# coding=utf-8
"""
    @project: MaxKB
    @file:   workflow_run.py
    @desc:   WorkflowRun endpoints (Gate 7 Track B list + Gate 8 Track B
             recovery).

    - FinanceWorkflowRunListView: read-only, paginated, filterable list.
      FINANCE_READ — any workspace member can see the runtime trail.
    - WorkflowRunRetryView: re-dispatch a failed/cancelled run as a NEW
      WorkflowRun row (history is never mutated). FINANCE_EDIT.
    - WorkflowRunCancelView: revoke a queued/running/retrying run and fail
      the underlying target. FINANCE_EDIT.

    Recovery design notes:
      - Retry creates a fresh WorkflowRun rather than reusing the old row,
        so the audit/history trail stays append-only. The old row keeps
        its terminal state.
      - The dispatch table maps a stored ``task_name`` back to its Celery
        task + the in-flight status the target should be reset to. This
        is the single source of truth for "how do I re-run this".
      - celery_app.control.revoke is best-effort and try/except guarded —
        a broker outage must not 500 the cancel endpoint; we still flip
        the DB rows so the UI unsticks.
"""
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from common.exception.app_exception import AppApiException, NotFound404
from common.utils.logger import maxkb_logger
from finance.models import WorkflowRun, WorkflowRunStatus
from finance.service.audit import audit_log

_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200

# Statuses a run may be retried from (terminal, non-success).
_RETRYABLE_STATUSES = (WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED)
# Statuses a run may be cancelled from (still in flight).
_CANCELLABLE_STATUSES = (
    WorkflowRunStatus.QUEUED,
    WorkflowRunStatus.RUNNING,
    WorkflowRunStatus.RETRYING,
)

# Dispatch table: stored ``task_name`` -> how to re-run it.
#   celery_attr   — attribute on ``finance.tasks`` to call ``.delay()`` on
#   target_kind   — 'MATERIALS_TASK' | 'DOC_GENERATION'
#   reset_status  — the in-flight status the target row is reset to so the
#                   UI immediately shows "work in progress" again
_TASK_DISPATCH = {
    'finance.materials.async_parse': {
        'celery_attr': 'async_parse',
        'target_kind': 'MATERIALS_TASK',
        'reset_status': 'parsing',
    },
    'finance.materials.async_match': {
        'celery_attr': 'async_match',
        'target_kind': 'MATERIALS_TASK',
        'reset_status': 'matching',
    },
    'finance.materials.async_pack': {
        'celery_attr': 'async_pack',
        'target_kind': 'MATERIALS_TASK',
        'reset_status': 'matching',
    },
    'finance.documents.async_generate': {
        'celery_attr': 'async_generate',
        'target_kind': 'DOC_GENERATION',
        'reset_status': 'generating',
    },
}


def _parse_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _to_dict(row: WorkflowRun) -> dict:
    return {
        'id': str(row.id),
        'workspace_id': row.workspace_id,
        'target_type': row.target_type,
        'target_id': str(row.target_id),
        'task_name': row.task_name,
        'celery_task_id': row.celery_task_id,
        'status': row.status,
        'started_at': row.started_at.isoformat() if row.started_at else None,
        'finished_at': row.finished_at.isoformat() if row.finished_at else None,
        'duration_ms': row.duration_ms,
        'error_message': row.error_message or '',
        'payload': row.payload or {},
        'retry_count': row.retry_count,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


class FinanceWorkflowRunListView(APIView):
    """GET /workspace/<wid>/workflow-run?target_type=&target_id=&status=&page=&size="""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List workflow runs'),
        operation_id=_('List workflow runs'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = WorkflowRun.objects.filter(workspace_id=workspace_id)
        target_type = (request.query_params.get('target_type') or '').strip()
        if target_type:
            qs = qs.filter(target_type=target_type)
        target_id = (request.query_params.get('target_id') or '').strip()
        if target_id:
            qs = qs.filter(target_id=target_id)
        status = (request.query_params.get('status') or '').strip()
        if status:
            qs = qs.filter(status=status)
        page = _parse_int(request.query_params.get('page'), _DEFAULT_PAGE)
        size = min(_parse_int(request.query_params.get('size'), _DEFAULT_SIZE), _MAX_SIZE)
        total = qs.count()
        offset = (page - 1) * size
        records = [_to_dict(r) for r in qs[offset: offset + size]]
        return result.success(
            result.Page(
                total=total,
                records=records,
                current_page=page,
                page_size=size,
            )
        )


# ---------- recovery helpers ---------------------------------------------


def _get_run_or_404(workspace_id, pk) -> WorkflowRun:
    run = WorkflowRun.objects.filter(id=pk, workspace_id=str(workspace_id)).first()
    if run is None:
        raise NotFound404(404, _('Workflow run not found'))
    return run


def _reset_target_status(target_kind: str, target_id, reset_status: str) -> None:
    """
    Drag the underlying MaterialsTask / DocumentGeneration back into an
    in-flight status so the worker (and the polling UI) see a fresh run.
    Best-effort: a failure here is logged, never raised — the new
    WorkflowRun row + Celery dispatch is what actually matters.
    """
    try:
        if target_kind == 'MATERIALS_TASK':
            from finance.models import MaterialsTask

            task = MaterialsTask.objects.filter(id=target_id, is_deleted=False).first()
            if task is not None:
                task.status = reset_status
                task.error_message = ''
                task.save(update_fields=['status', 'error_message', 'updated_at'])
        elif target_kind == 'DOC_GENERATION':
            from finance.models import DocumentGeneration

            gen = DocumentGeneration.objects.filter(id=target_id).first()
            if gen is not None:
                gen.status = reset_status
                gen.error_message = ''
                gen.save(update_fields=['status', 'error_message', 'updated_at'])
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_run] _reset_target_status '
            f'({target_kind}/{target_id}) failed: {exc}',
            exc_info=True,
        )


def _fail_target_cancelled(target_kind: str, target_id) -> None:
    """Set the underlying target to FAILED with a 'cancelled by user' note."""
    try:
        if target_kind == 'MATERIALS_TASK':
            from finance.models import MaterialsTask, MaterialsTaskStatus

            task = MaterialsTask.objects.filter(id=target_id, is_deleted=False).first()
            if task is not None:
                task.status = MaterialsTaskStatus.FAILED
                task.error_message = 'Cancelled by user'
                task.save(update_fields=['status', 'error_message', 'updated_at'])
        elif target_kind == 'DOC_GENERATION':
            from finance.models import DocumentGeneration, GenerationStatus

            gen = DocumentGeneration.objects.filter(id=target_id).first()
            if gen is not None:
                gen.status = GenerationStatus.FAILED
                gen.error_message = 'Cancelled by user'
                gen.save(update_fields=['status', 'error_message', 'updated_at'])
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.error(
            f'[finance.workflow_run] _fail_target_cancelled '
            f'({target_kind}/{target_id}) failed: {exc}',
            exc_info=True,
        )


class WorkflowRunRetryView(APIView):
    """POST /workspace/<wid>/workflow-run/<pk>/retry

    Re-dispatches the task behind a failed/cancelled run. A NEW WorkflowRun
    row is created (queued); the old row is left untouched so history stays
    append-only. The underlying target is reset to its in-flight status.
    """

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Retry workflow run'),
        operation_id=_('Retry workflow run'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action='UPDATE', target_type='OTHER')
    def post(self, request: Request, workspace_id, pk):
        run = _get_run_or_404(workspace_id, pk)
        if run.status not in _RETRYABLE_STATUSES:
            raise AppApiException(
                400,
                _('Only failed or cancelled runs can be retried'),
            )
        dispatch = _TASK_DISPATCH.get(run.task_name)
        if dispatch is None:
            raise AppApiException(
                400,
                _('Unknown task; cannot retry: ') + str(run.task_name),
            )

        from finance.service.workflow_runtime import create_queued_run

        # New queued row — preserves the original payload so the worker
        # re-runs with the same inputs (e.g. user_max_sensitivity).
        new_run = create_queued_run(
            workspace_id=workspace_id,
            target_type=run.target_type,
            target_id=run.target_id,
            task_name=run.task_name,
            payload=dict(run.payload or {}),
        )

        # Reset the underlying target so the UI shows work-in-flight again.
        _reset_target_status(
            dispatch['target_kind'], run.target_id, dispatch['reset_status']
        )

        # Dispatch the Celery task. Guarded — if the broker is unreachable
        # the queued row still exists and a later retry / worker recovery
        # can pick it up; we surface the failure but don't 500 destructively.
        new_run_id = str(new_run.id) if new_run is not None else None
        try:
            import finance.tasks as finance_tasks

            celery_task = getattr(finance_tasks, dispatch['celery_attr'])
            payload = run.payload or {}
            if run.task_name == 'finance.materials.async_match':
                celery_task.delay(
                    str(run.target_id),
                    user_max_sensitivity=payload.get('user_max_sensitivity'),
                    run_id=new_run_id,
                )
            elif run.task_name == 'finance.materials.async_pack':
                celery_task.delay(
                    str(run.target_id),
                    item_groups=payload.get('item_groups'),
                    run_id=new_run_id,
                )
            else:
                # async_parse / async_generate — single positional id.
                celery_task.delay(str(run.target_id), run_id=new_run_id)
        except Exception as exc:  # noqa: BLE001
            maxkb_logger.error(
                f'[finance.workflow_run] retry dispatch failed for '
                f'{run.task_name} ({run.target_id}): {exc}',
                exc_info=True,
            )
            raise AppApiException(
                500,
                _('Failed to dispatch retry task; the task queue may be down'),
            )

        return result.success(
            {
                'retried_from': str(run.id),
                'new_run': _to_dict(new_run) if new_run is not None else None,
            }
        )


class WorkflowRunCancelView(APIView):
    """POST /workspace/<wid>/workflow-run/<pk>/cancel

    Revokes a queued/running/retrying run via Celery (best-effort) and
    flips the WorkflowRun + underlying target into a terminal state so the
    UI stops showing a spinner forever.
    """

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Cancel workflow run'),
        operation_id=_('Cancel workflow run'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action='UPDATE', target_type='OTHER')
    def post(self, request: Request, workspace_id, pk):
        run = _get_run_or_404(workspace_id, pk)
        if run.status not in _CANCELLABLE_STATUSES:
            raise AppApiException(
                400,
                _('Only queued, running or retrying runs can be cancelled'),
            )

        # Best-effort Celery revoke. terminate=False — we don't SIGKILL a
        # running worker process (that risks corrupt partial state); we
        # just stop it from being picked up / re-queued. A broker outage
        # here must NOT 500: we still flip the DB rows below.
        if run.celery_task_id:
            try:
                from ops import celery_app

                celery_app.control.revoke(run.celery_task_id, terminate=False)
            except Exception as exc:  # noqa: BLE001
                maxkb_logger.warning(
                    f'[finance.workflow_run] celery revoke failed for '
                    f'{run.celery_task_id}: {exc}'
                )

        run.status = WorkflowRunStatus.CANCELLED
        run.finished_at = timezone.now()
        if not run.error_message:
            run.error_message = 'Cancelled by user'
        run.save(
            update_fields=['status', 'finished_at', 'error_message', 'updated_at']
        )

        dispatch = _TASK_DISPATCH.get(run.task_name)
        target_kind = dispatch['target_kind'] if dispatch else (run.target_type or '')
        _fail_target_cancelled(target_kind, run.target_id)

        return result.success(_to_dict(run))

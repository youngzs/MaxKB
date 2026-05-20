# coding=utf-8
"""
    @project: MaxKB
    @file： materials_task.py
    @desc: REST endpoints for the MaterialsTask workflow (Gate 4 Track A).

    State machine (synchronous, single-process — Gate 5 will offload the
    heavy steps to Celery):
        create               → DRAFT
        parse                → DRAFT (parsed_items populated)
        match                → DRAFT (matched_documents populated, with
                                 sensitivity gate applied)
        selection PUT        → DRAFT (curates selected_documents)
        summarize            → DRAFT (writes ai_summary into matched_documents)
        pack                 → APPROVED (zip_oss_key populated)
        submit-review        → PENDING_REVIEW
        review pass          → APPROVED
        review reject        → REJECTED
        zip download         → no state change

    `SENT` is reserved for Gate 5 (external delivery) and is intentionally
    not reachable from the Gate 4 surface.

    Sensitivity model: every match-time SQL query funnels through
    `knowledge_matcher.match_documents_for_items`, which inserts a
    `sensitivity_level__in=levels_up_to(user_max)` filter at the ORM layer.
    The caller's `user_max` is derived from
    `sensitivity.get_user_max_sensitivity(request.user, workspace_id)`.
"""
from __future__ import annotations

import os
import urllib.parse

from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from common.exception.app_exception import AppApiException, NotFound404
from finance.models import (
    FinanceAuditAction,
    FinanceAuditTargetType,
    FinanceProject,
    MaterialsTask,
    MaterialsTaskStatus,
)
from finance.serializers.materials_task import (
    MaterialsTaskCreateSerializer,
    MaterialsTaskOutputSerializer,
    MaterialsTaskPackSerializer,
    MaterialsTaskReviewSerializer,
    MaterialsTaskUpdateSelectionSerializer,
    MaterialsTaskUpdateSerializer,
)
from finance.service.audit import audit_log
from finance.service.document_generator import _load_bytes, _save_bytes
from finance.service.knowledge_matcher import match_documents_for_items
from finance.service.requirement_parser import parse_requirement_list
from finance.service.sensitivity import get_user_max_sensitivity
from finance.service.summary_generator import generate_summary_for_document
from finance.service.zip_packager import pack_documents_grouped

_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200
_ZIP_MIME = 'application/zip'
_REQUIREMENT_FILE_SOURCE_ID = 'FINANCE_MATERIALS_REQUIREMENT'


def _async_enabled() -> bool:
    """
    Feature flag for the Gate 7 Track B async pipeline.

    Defaults to True (async). Set FINANCE_ASYNC_ENABLED=0/false/no to fall
    back to the synchronous Gate 4 code path — useful when Celery is
    unavailable or for deterministic tests.
    """
    raw = (os.environ.get('FINANCE_ASYNC_ENABLED') or '').strip().lower()
    if raw in {'0', 'false', 'no', 'off'}:
        return False
    return True


# ----- helpers ---------------------------------------------------------


def _parse_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _paginate(queryset, query_params):
    page = _parse_int(query_params.get('page'), _DEFAULT_PAGE)
    size = min(_parse_int(query_params.get('size'), _DEFAULT_SIZE), _MAX_SIZE)
    total = queryset.count()
    offset = (page - 1) * size
    records = list(queryset[offset: offset + size])
    return total, page, size, records


def _get_or_404(workspace_id, pk) -> MaterialsTask:
    instance = MaterialsTask.objects.filter(
        id=pk, workspace_id=workspace_id, is_deleted=False
    ).first()
    if instance is None:
        raise NotFound404(404, _('Materials task not found'))
    return instance


def _project_or_404(workspace_id, project_id) -> FinanceProject:
    project = FinanceProject.objects.filter(
        id=project_id, workspace_id=workspace_id, is_deleted=False
    ).first()
    if project is None:
        raise NotFound404(404, _('Project not found'))
    return project


def _extract_text_from_upload(uploaded) -> str:
    """
    Best-effort text extraction for a requirement-list upload.

    Gate 4 supports `.txt` directly and `.docx` via python-docx. PDF is
    deferred to Gate 5 (LLM-based extraction works much better there than
    pdfminer for the messy formats investors actually send).
    """
    name = (getattr(uploaded, 'name', '') or '').lower()
    raw = uploaded.read()
    if name.endswith('.txt'):
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return raw.decode('utf-8', errors='replace')
    if name.endswith('.docx'):
        try:
            from io import BytesIO

            import docx  # python-docx

            doc = docx.Document(BytesIO(raw))
            return '\n'.join(p.text for p in doc.paragraphs if p.text)
        except Exception:  # noqa: BLE001 — degrade to empty so the row still saves
            return ''
    # .pdf and friends — TODO(Gate 5)
    return ''


# ----- testable state-machine helpers (decorator-free) ---------------


def _do_parse(instance: MaterialsTask, workspace_id) -> MaterialsTask:
    text = instance.requirement_text or ''
    if not text:
        # Try the uploaded file (if any) as a fallback. Without that path
        # there is nothing to parse.
        if not instance.requirement_file_oss_key:
            raise AppApiException(400, _('Materials task has no requirement text or file'))
        try:
            raw = _load_bytes(instance.requirement_file_oss_key)
            text = raw.decode('utf-8', errors='replace')
        except Exception as e:  # noqa: BLE001
            raise AppApiException(400, _('Failed to load requirement file: ') + repr(e))

    items = parse_requirement_list(text, workspace_id=workspace_id)
    instance.parsed_items = items
    instance.error_message = ''
    if instance.status == MaterialsTaskStatus.FAILED:
        instance.status = MaterialsTaskStatus.DRAFT
    instance.save(
        update_fields=['parsed_items', 'error_message', 'status', 'updated_at']
    )
    return instance


def _do_match(instance: MaterialsTask, workspace_id, user_max_sensitivity) -> MaterialsTask:
    if not instance.parsed_items:
        raise AppApiException(400, _('Parse requirement items before matching'))
    matches = match_documents_for_items(
        items=instance.parsed_items,
        workspace_id=workspace_id,
        project_id=instance.project_id,
        user_max_sensitivity=user_max_sensitivity,
    )
    instance.matched_documents = matches
    instance.error_message = ''
    instance.save(
        update_fields=['matched_documents', 'error_message', 'updated_at']
    )
    return instance


# 允许编辑（PUT requirement_text / parsed_items / title）的状态白名单。
# 一旦任务进入 PENDING_REVIEW 或后续审核/打包/发送状态，需求清单就要冻结 ——
# 否则就破坏审计链：审核者拍板的内容 ≠ 实际打包发送的内容。
_EDITABLE_STATUSES = frozenset(
    [
        MaterialsTaskStatus.DRAFT,
        MaterialsTaskStatus.FAILED,
        # PARSING / MATCHING 都是过渡态（异步 task 持有的中间状态），用户
        # 看到的多半是僵死的任务，允许编辑 + 重新触发更友好。
        MaterialsTaskStatus.PARSING,
        MaterialsTaskStatus.MATCHING,
    ]
)


def _do_update(instance: MaterialsTask, payload: dict) -> MaterialsTask:
    """
    Patch the editable subset of a MaterialsTask.

    Only DRAFT/FAILED/PARSING/MATCHING tasks are editable —— reviewed or
    sent tasks are immutable for audit integrity. `parsed_items` updates
    are accepted verbatim (no re-parse) so users can manually curate the
    requirement list. Call /parse separately to re-run the LLM.

    Returns the updated instance. Never silently no-ops on unknown
    keys — those are rejected at the serializer layer.
    """
    if instance.status not in _EDITABLE_STATUSES:
        raise AppApiException(
            400,
            _('Cannot edit materials task in %(status)s status') % {'status': instance.status},
        )

    update_fields: list[str] = []
    if 'title' in payload:
        instance.title = payload['title']
        update_fields.append('title')
    if 'requirement_text' in payload:
        instance.requirement_text = payload['requirement_text']
        update_fields.append('requirement_text')
    if 'parsed_items' in payload:
        # serializer 已经按 schema 校验；这里 normalise booleans 和 strip 空白。
        instance.parsed_items = [
            {
                'key': item['key'].strip(),
                'label': item['label'].strip(),
                'description': (item.get('description') or '').strip(),
                'required': bool(item.get('required', True)),
            }
            for item in payload['parsed_items']
        ]
        update_fields.append('parsed_items')

    if update_fields:
        update_fields.append('updated_at')
        instance.save(update_fields=update_fields)
    return instance


def _do_update_selection(
    instance: MaterialsTask, selected_documents, matched_documents=None
) -> MaterialsTask:
    instance.selected_documents = [str(s) for s in (selected_documents or [])]
    update_fields = ['selected_documents', 'updated_at']
    if matched_documents is not None:
        instance.matched_documents = matched_documents
        update_fields.insert(1, 'matched_documents')
    instance.save(update_fields=update_fields)
    return instance


def _do_summarize(instance: MaterialsTask, workspace_id) -> MaterialsTask:
    if not instance.matched_documents:
        raise AppApiException(400, _('No matched documents to summarize'))
    selected = set(str(s) for s in instance.selected_documents or [])
    updated: list[dict] = []
    for row in instance.matched_documents or []:
        row = dict(row)
        doc_id = row.get('document_id')
        # Only summarise rows the user has actually picked (saves Gate 5 tokens).
        if doc_id and (not selected or doc_id in selected):
            row['ai_summary'] = generate_summary_for_document(doc_id, workspace_id)
        updated.append(row)
    instance.matched_documents = updated
    instance.save(update_fields=['matched_documents', 'updated_at'])
    return instance


def _build_groups_from_state(instance: MaterialsTask) -> list[dict]:
    """
    Derive `[{folder, document_ids}]` from `parsed_items` + `selected_documents`.

    Each parsed item becomes a folder named `NN_<label>` (preserving order).
    Documents selected for that item are placed under that folder. Anything
    selected but never matched ends up in a `99_other` folder.
    """
    selected = set(str(s) for s in instance.selected_documents or [])
    if not selected:
        return []
    # Map (item_key → list[document_id]) using matched_documents as the
    # source of truth for what belongs where.
    bucket: dict[str, list[str]] = {}
    for row in instance.matched_documents or []:
        doc_id = str(row.get('document_id', ''))
        if doc_id and doc_id in selected:
            bucket.setdefault(str(row.get('item_key', '')), []).append(doc_id)

    groups: list[dict] = []
    used: set[str] = set()
    for idx, item in enumerate(instance.parsed_items or [], start=1):
        key = str(item.get('key', ''))
        label = str(item.get('label', '')) or key or f'item_{idx}'
        doc_ids = bucket.get(key, [])
        if not doc_ids:
            continue
        used.update(doc_ids)
        groups.append({'folder': f'{idx:02d}_{label}', 'document_ids': doc_ids})

    leftover = [d for d in selected if d not in used]
    if leftover:
        groups.append({'folder': '99_other', 'document_ids': leftover})
    return groups


def _do_pack(
    instance: MaterialsTask, workspace_id, override_groups=None
) -> MaterialsTask:
    if not instance.selected_documents:
        raise AppApiException(400, _('Select documents before packing'))
    groups = override_groups or _build_groups_from_state(instance)
    if not groups:
        raise AppApiException(
            400, _('Unable to derive zip layout; provide item_groups explicitly')
        )
    filename = f'materials-{instance.id}.zip'
    zip_key = pack_documents_grouped(
        item_groups=groups,
        workspace_id=workspace_id,
        output_filename=filename,
    )
    instance.zip_oss_key = zip_key
    # Pack is the terminal "I'm ready" action — flip to APPROVED so the
    # user can either submit-review (for a 2nd-pair-of-eyes review) or
    # download immediately. Gate 5 will gate this behind a workspace
    # setting (review-required vs. self-serve).
    instance.status = MaterialsTaskStatus.APPROVED
    instance.error_message = ''
    instance.save(
        update_fields=['zip_oss_key', 'status', 'error_message', 'updated_at']
    )
    return instance


def _do_submit_review(instance: MaterialsTask) -> MaterialsTask:
    if not instance.zip_oss_key:
        raise AppApiException(400, _('Pack the zip before submitting for review'))
    if instance.status not in (
        MaterialsTaskStatus.DRAFT,
        MaterialsTaskStatus.APPROVED,
    ):
        raise AppApiException(
            400, _('Only draft or self-approved tasks can be submitted for review')
        )
    instance.status = MaterialsTaskStatus.PENDING_REVIEW
    instance.save(update_fields=['status', 'updated_at'])
    return instance


def _do_review(instance: MaterialsTask, action: str, comment: str, reviewer_id) -> MaterialsTask:
    if instance.status != MaterialsTaskStatus.PENDING_REVIEW:
        raise AppApiException(
            400, _('Only pending_review tasks can be reviewed')
        )
    if action == 'pass':
        instance.status = MaterialsTaskStatus.APPROVED
    elif action == 'reject':
        instance.status = MaterialsTaskStatus.REJECTED
    else:
        raise AppApiException(400, _('Unknown review action'))
    instance.reviewer_id = reviewer_id
    instance.reviewed_at = timezone.now()
    instance.review_comment = comment or ''
    instance.save(
        update_fields=[
            'status',
            'reviewer_id',
            'reviewed_at',
            'review_comment',
            'updated_at',
        ]
    )
    return instance


# ----- views -----------------------------------------------------------


class MaterialsTaskListView(APIView):
    """GET (list, paginated, filterable) + POST (create)."""

    authentication_classes = [TokenAuth]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        methods=['GET'],
        summary=_('List materials tasks'),
        operation_id=_('List materials tasks'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = MaterialsTask.objects.filter(
            workspace_id=workspace_id, is_deleted=False
        )
        project_id = (request.query_params.get('project_id') or '').strip()
        if project_id:
            qs = qs.filter(project_id=project_id)
        status = (request.query_params.get('status') or '').strip()
        if status:
            qs = qs.filter(status=status)
        total, page, size, records = _paginate(qs, request.query_params)
        serializer = MaterialsTaskOutputSerializer(records, many=True)
        return result.success(
            result.Page(
                total=total, records=serializer.data,
                current_page=page, page_size=size,
            )
        )

    @extend_schema(
        methods=['POST'],
        summary=_('Create materials task'),
        request=MaterialsTaskCreateSerializer,
        responses=MaterialsTaskOutputSerializer,
        tags=[_('Finance')],  # type: ignore
        operation_id=_('Create materials task'),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.CREATE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def post(self, request: Request, workspace_id):
        body = MaterialsTaskCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data

        _project_or_404(workspace_id, payload['project_id'])

        text = payload.get('requirement_text') or ''
        uploaded = payload.get('requirement_file')
        oss_key = ''
        if uploaded is not None:
            # Persist the raw upload to OSS so we keep an auditable
            # original. Extract text inline for an immediate parse later.
            file_bytes = uploaded.read()
            # Rewind the buffer so the extractor still sees content.
            uploaded.seek(0)
            oss_key = _save_bytes(
                file_bytes,
                getattr(uploaded, 'name', 'requirement.txt'),
                _REQUIREMENT_FILE_SOURCE_ID,
            )
            if not text:
                text = _extract_text_from_upload(uploaded)

        task = MaterialsTask.objects.create(
            workspace_id=workspace_id,
            project_id=payload['project_id'],
            title=payload['title'],
            requirement_text=text,
            requirement_file_oss_key=oss_key,
            status=MaterialsTaskStatus.DRAFT,
            created_by=request.user.id,
        )
        return result.success(MaterialsTaskOutputSerializer(task).data)


class MaterialsTaskDetailView(APIView):
    """GET detail + DELETE (soft)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Get materials task'),
        operation_id=_('Get materials task'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        return result.success(MaterialsTaskOutputSerializer(instance).data)

    @extend_schema(
        methods=['PUT'],
        summary=_('Update materials task'),
        request=MaterialsTaskUpdateSerializer,
        responses=MaterialsTaskOutputSerializer,
        tags=[_('Finance')],  # type: ignore
        operation_id=_('Update materials task'),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def put(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        body = MaterialsTaskUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        # validated_data 只含显式传入的字段，未传的字段不会出现 —— 用 dict()
        # 显式持有再交给 _do_update，避免 partial-update 时把缺省字段也覆盖掉。
        instance = _do_update(instance, dict(body.validated_data))
        return result.success(MaterialsTaskOutputSerializer(instance).data)

    @extend_schema(
        methods=['DELETE'],
        summary=_('Delete materials task'),
        operation_id=_('Delete materials task'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.DELETE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def delete(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        return result.success({'id': str(instance.id)})


class MaterialsTaskParseView(APIView):
    """POST /<pk>/parse — parse requirement_text/file into structured items."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Parse requirement list'),
        operation_id=_('Parse requirement list'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def post(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        if _async_enabled():
            from finance.service.workflow_runtime import create_queued_run
            from finance.tasks import async_parse

            # Capture the queued-run id so the worker can promote it once
            # it picks the task up. State transition to PARSING is
            # performed inside the task to avoid a moment where status
            # says PARSING but no run row exists yet.
            wr = create_queued_run(
                workspace_id=workspace_id,
                target_type='MATERIALS_TASK',
                target_id=instance.id,
                task_name='finance.materials.async_parse',
                payload={'workspace_id': str(workspace_id)},
            )
            instance.status = MaterialsTaskStatus.PARSING
            instance.error_message = ''
            instance.save(update_fields=['status', 'error_message', 'updated_at'])
            async_parse.delay(str(instance.id), run_id=str(wr.id) if wr else None)
        else:
            instance = _do_parse(instance, workspace_id=workspace_id)
        return result.success(MaterialsTaskOutputSerializer(instance).data)


class MaterialsTaskMatchView(APIView):
    """POST /<pk>/match — sensitivity-gated knowledge match per item."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Match documents for materials task'),
        operation_id=_('Match materials task'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def post(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        user_max = get_user_max_sensitivity(request.user, workspace_id)
        if _async_enabled():
            from finance.service.workflow_runtime import create_queued_run
            from finance.tasks import async_match

            wr = create_queued_run(
                workspace_id=workspace_id,
                target_type='MATERIALS_TASK',
                target_id=instance.id,
                task_name='finance.materials.async_match',
                payload={
                    'workspace_id': str(workspace_id),
                    'user_max_sensitivity': user_max,
                },
            )
            instance.status = MaterialsTaskStatus.MATCHING
            instance.error_message = ''
            instance.save(update_fields=['status', 'error_message', 'updated_at'])
            async_match.delay(
                str(instance.id),
                user_max_sensitivity=user_max,
                run_id=str(wr.id) if wr else None,
            )
        else:
            instance = _do_match(
                instance, workspace_id=workspace_id, user_max_sensitivity=user_max
            )
        return result.success(MaterialsTaskOutputSerializer(instance).data)


class MaterialsTaskSelectionView(APIView):
    """PUT /<pk>/selection — curate final document list."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['PUT'],
        summary=_('Update materials task selection'),
        request=MaterialsTaskUpdateSelectionSerializer,
        responses=MaterialsTaskOutputSerializer,
        operation_id=_('Update materials task selection'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def put(self, request: Request, workspace_id, pk):
        body = MaterialsTaskUpdateSelectionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        instance = _get_or_404(workspace_id, pk)
        instance = _do_update_selection(
            instance,
            selected_documents=payload['selected_documents'],
            matched_documents=payload.get('matched_documents'),
        )
        return result.success(MaterialsTaskOutputSerializer(instance).data)


class MaterialsTaskSummarizeView(APIView):
    """POST /<pk>/summarize — (re)generate AI summaries for selected docs."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Generate AI summaries'),
        operation_id=_('Summarize materials task'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def post(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        instance = _do_summarize(instance, workspace_id=workspace_id)
        return result.success(MaterialsTaskOutputSerializer(instance).data)


class MaterialsTaskPackView(APIView):
    """POST /<pk>/pack — build the final zip and persist its OSS key."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Pack materials task into zip'),
        request=MaterialsTaskPackSerializer,
        responses=MaterialsTaskOutputSerializer,
        operation_id=_('Pack materials task'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def post(self, request: Request, workspace_id, pk):
        body = MaterialsTaskPackSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        instance = _get_or_404(workspace_id, pk)
        if _async_enabled():
            from finance.service.workflow_runtime import create_queued_run
            from finance.tasks import async_pack

            wr = create_queued_run(
                workspace_id=workspace_id,
                target_type='MATERIALS_TASK',
                target_id=instance.id,
                task_name='finance.materials.async_pack',
                payload={'workspace_id': str(workspace_id)},
            )
            # MATCHING is reused as the "work in progress" indicator for
            # the pack step; the UI's `isTransient` already covers it.
            instance.status = MaterialsTaskStatus.MATCHING
            instance.error_message = ''
            instance.save(update_fields=['status', 'error_message', 'updated_at'])
            async_pack.delay(
                str(instance.id),
                item_groups=payload.get('item_groups'),
                run_id=str(wr.id) if wr else None,
            )
        else:
            instance = _do_pack(
                instance,
                workspace_id=workspace_id,
                override_groups=payload.get('item_groups'),
            )
        return result.success(MaterialsTaskOutputSerializer(instance).data)


class MaterialsTaskSubmitReviewView(APIView):
    """POST /<pk>/submit-review — flip to PENDING_REVIEW."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Submit materials task for review'),
        operation_id=_('Submit materials task for review'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def post(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        instance = _do_submit_review(instance)
        return result.success(MaterialsTaskOutputSerializer(instance).data)


class MaterialsTaskReviewView(APIView):
    """POST /<pk>/review — pass or reject a pending_review task."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Review materials task'),
        request=MaterialsTaskReviewSerializer,
        responses=MaterialsTaskOutputSerializer,
        operation_id=_('Review materials task'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_REVIEW.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def post(self, request: Request, workspace_id, pk):
        body = MaterialsTaskReviewSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        instance = _get_or_404(workspace_id, pk)
        # Decorator-free audit so we can pick the right action per branch.
        action_label = (
            FinanceAuditAction.REVIEW_PASS
            if payload['action'] == 'pass'
            else FinanceAuditAction.REVIEW_REJECT
        )
        instance = _do_review(
            instance,
            action=payload['action'],
            comment=payload.get('comment') or '',
            reviewer_id=request.user.id,
        )
        # Manual audit-log call (mirrors finance.service.audit.log_event).
        from finance.service.audit import _get_ip, _get_ua, _safe_request_snapshot, log_event

        log_event(
            workspace_id=workspace_id,
            actor_id=request.user.id,
            target_type=FinanceAuditTargetType.MATERIALS_TASK,
            target_id=str(instance.id),
            action=action_label,
            payload=_safe_request_snapshot(request),
            ip=_get_ip(request),
            user_agent=_get_ua(request),
        )
        return result.success(MaterialsTaskOutputSerializer(instance).data)


class MaterialsTaskZipDownloadView(APIView):
    """GET /<pk>/zip — stream the packed zip."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Download materials task zip'),
        operation_id=_('Download materials task zip'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.DOWNLOAD, target_type=FinanceAuditTargetType.MATERIALS_TASK)
    def get(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        if not instance.zip_oss_key:
            raise AppApiException(400, _('Materials task has not been packed yet'))
        zip_bytes = _load_bytes(instance.zip_oss_key)
        filename = f'materials-{instance.id}.zip'
        response = HttpResponse(zip_bytes, content_type=_ZIP_MIME)
        encoded = urllib.parse.quote(filename)
        response['Content-Disposition'] = (
            f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
        )
        return response

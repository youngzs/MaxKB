# coding=utf-8
"""
    @project: MaxKB
    @file： document_generation.py
    @desc: DocumentGeneration REST endpoints — covers the state machine
    GENERATING → PENDING_REVIEW → CONFIRMED / REVOKED plus preview/download/
    ai-fill.

    Permission model:
      - FINANCE_READ for list/detail/preview/download
      - FINANCE_EDIT for create
      - FINANCE_REVIEW for confirm/revoke
      - FINANCE_EDIT for AI-fill (writing into an in-progress draft).
"""
import urllib.parse

from django.http import HttpResponse
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
from finance.models import (
    DocumentGeneration,
    DocumentTemplate,
    FinanceAuditAction,
    FinanceAuditTargetType,
    FinanceProject,
    GenerationStatus,
)
from finance.serializers.document_generation import (
    AIFillRequestSerializer,
    DocumentGenerationCreateSerializer,
    DocumentGenerationOutputSerializer,
)
from finance.service.audit import audit_log
from finance.service.document_generator import (
    _load_bytes,
    render_to_html,
    trigger_generation,
)
from finance.service.llm import chat_completion

from common.utils.logger import maxkb_logger

_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200
_DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


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


def _get_or_404(workspace_id, pk) -> DocumentGeneration:
    instance = DocumentGeneration.objects.filter(id=pk, workspace_id=workspace_id).first()
    if instance is None:
        raise NotFound404(404, _('Generation not found'))
    return instance


# ---- testable core helpers (extracted so unit tests can bypass the
#      auth/audit decorators without reimplementing the state machine) ----


def _do_confirm(instance: DocumentGeneration, actor_id) -> DocumentGeneration:
    if instance.status != GenerationStatus.PENDING_REVIEW:
        raise AppApiException(
            400, _('Only pending_review generations can be confirmed')
        )
    instance.status = GenerationStatus.CONFIRMED
    instance.reviewer_id = actor_id
    instance.reviewed_at = timezone.now()
    instance.save(update_fields=['status', 'reviewer_id', 'reviewed_at', 'updated_at'])
    return instance


def _do_revoke(instance: DocumentGeneration, actor_id) -> DocumentGeneration:
    if instance.status not in (GenerationStatus.CONFIRMED, GenerationStatus.PENDING_REVIEW):
        raise AppApiException(
            400, _('Only pending_review or confirmed generations can be revoked')
        )
    instance.status = GenerationStatus.REVOKED
    instance.reviewer_id = actor_id
    instance.reviewed_at = timezone.now()
    instance.save(update_fields=['status', 'reviewer_id', 'reviewed_at', 'updated_at'])
    return instance


_AI_FILL_SYSTEM_PROMPT = (
    '你是合规融资文档撰写助手。请根据上下文，为下面这个占位符生成准确、专业的填充内容。\n'
    '  - 占位符标签：{label}\n'
    '  - 类型：{type}\n'
    '  - 提示：{ai_hint}\n'
    '  - 项目：{project_name} (代码 {project_code}, 金额 {target_amount} {currency})\n'
    '直接输出填充内容文本，不要加引号或额外说明。'
)


def _do_ai_fill(template: DocumentTemplate, project: FinanceProject,
                placeholder_keys, workspace_id: str = 'default') -> dict:
    """
    Generate AI-filled values for each requested placeholder key declared on
    the template. Unknown keys are silently dropped.

    Each placeholder is rendered into its own single-turn LLM prompt
    parameterised by project + template metadata. Any failure mode (no LLM
    configured, model error, empty response, oversized response) falls back
    to the legacy stub string `[AI 待生成: <label>]` for that key, so the
    overall call always returns a dict with every requested-and-known key.

    The function MUST NOT raise; if anything explodes mid-loop we return
    the stub-filled dict for whatever we've assembled so far.
    """
    wanted = set(placeholder_keys)
    placeholders_by_key = {p.get('key'): p for p in (template.placeholders or [])}
    filled: dict = {}
    # Hard ceiling on a single AI-fill response — keeps a misbehaving model
    # from blowing up downstream docx rendering with multi-KB blobs.
    max_chars = 2048

    try:
        for key in wanted:
            meta = placeholders_by_key.get(key)
            if meta is None:
                continue
            label = meta.get('label') or key
            ph_type = meta.get('type') or 'text'
            ai_hint = meta.get('ai_hint') or '无'
            stub = f'[AI 待生成: {label}]'

            try:
                system_prompt = _AI_FILL_SYSTEM_PROMPT.format(
                    label=label,
                    type=ph_type,
                    ai_hint=ai_hint,
                    project_name=project.name,
                    project_code=project.code or '',
                    target_amount=project.target_amount,
                    currency=project.currency,
                )
                text = chat_completion(workspace_id, system_prompt, '请生成内容。')
            except Exception as e:  # noqa: BLE001 — never propagate
                maxkb_logger.warning(f'[finance.ai_fill] chat_completion raised for {key}: {e}')
                filled[key] = stub
                continue

            if not text:
                filled[key] = stub
                continue
            content = text.strip()
            if not content or len(content) > max_chars:
                filled[key] = stub
                continue
            filled[key] = content
    except Exception as e:  # noqa: BLE001 — bulk fallback
        maxkb_logger.error(f'[finance.ai_fill] unexpected failure, returning partial: {e}', exc_info=True)
        # Backfill anything not yet processed with the stub.
        for key in wanted:
            if key in filled:
                continue
            meta = placeholders_by_key.get(key)
            if meta is None:
                continue
            label = meta.get('label') or key
            filled[key] = f'[AI 待生成: {label}]'

    return filled


class DocumentGenerationListView(APIView):
    """GET (list) + POST (create + trigger rendering synchronously)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List document generations'),
        operation_id=_('List document generations'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = DocumentGeneration.objects.filter(workspace_id=workspace_id)
        project_id = (request.query_params.get('project_id') or '').strip()
        if project_id:
            qs = qs.filter(project_id=project_id)
        template_id = (request.query_params.get('template_id') or '').strip()
        if template_id:
            qs = qs.filter(template_id=template_id)
        status = (request.query_params.get('status') or '').strip()
        if status:
            qs = qs.filter(status=status)
        total, page, size, records = _paginate(qs, request.query_params)
        serializer = DocumentGenerationOutputSerializer(records, many=True)
        return result.success(
            result.Page(total=total, records=serializer.data, current_page=page, page_size=size)
        )

    @extend_schema(
        methods=['POST'],
        summary=_('Create document generation'),
        request=DocumentGenerationCreateSerializer,
        responses=DocumentGenerationOutputSerializer,
        tags=[_('Finance')],  # type: ignore
        operation_id=_('Create document generation'),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.CREATE, target_type=FinanceAuditTargetType.DOC_GENERATION)
    def post(self, request: Request, workspace_id):
        body = DocumentGenerationCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data

        project = FinanceProject.objects.filter(
            id=payload['project_id'], workspace_id=workspace_id, is_deleted=False
        ).first()
        if project is None:
            raise NotFound404(404, _('Project not found'))
        template = DocumentTemplate.objects.filter(
            id=payload['template_id'], workspace_id=workspace_id, is_deleted=False
        ).first()
        if template is None:
            raise NotFound404(404, _('Template not found'))

        gen = DocumentGeneration.objects.create(
            workspace_id=workspace_id,
            project_id=project.id,
            template_id=template.id,
            template_version_snapshot=template.version,
            placeholder_values=payload.get('placeholder_values') or {},
            status=GenerationStatus.GENERATING,
            created_by=request.user.id,
        )
        # Synchronous render — Gate 3 MVP; small docs render in <1s. Gate 5
        # will wrap trigger_generation in a Celery task and have this view
        # return immediately while status=GENERATING.
        trigger_generation(gen.id)
        gen.refresh_from_db()
        return result.success(DocumentGenerationOutputSerializer(gen).data)


class DocumentGenerationDetailView(APIView):
    """GET detail."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Get document generation'),
        operation_id=_('Get document generation'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        return result.success(DocumentGenerationOutputSerializer(instance).data)


class DocumentGenerationConfirmView(APIView):
    """POST confirm → PENDING_REVIEW must transition to CONFIRMED."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Confirm document generation'),
        operation_id=_('Confirm document generation'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_REVIEW.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.REVIEW_PASS, target_type=FinanceAuditTargetType.DOC_GENERATION)
    def post(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        instance = _do_confirm(instance, request.user.id)
        return result.success(DocumentGenerationOutputSerializer(instance).data)


class DocumentGenerationRevokeView(APIView):
    """POST revoke → CONFIRMED or PENDING_REVIEW go to REVOKED."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Revoke document generation'),
        operation_id=_('Revoke document generation'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_REVIEW.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.REVIEW_REJECT, target_type=FinanceAuditTargetType.DOC_GENERATION)
    def post(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        instance = _do_revoke(instance, request.user.id)
        return result.success(DocumentGenerationOutputSerializer(instance).data)


class DocumentGenerationPreviewView(APIView):
    """GET HTML preview (just the body fragment)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Preview document generation as HTML'),
        operation_id=_('Preview document generation'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        if not instance.output_oss_key:
            raise AppApiException(400, _('Generation has no rendered output yet'))
        html = render_to_html(instance.output_oss_key)
        return result.success({'html': html})


class DocumentGenerationDownloadView(APIView):
    """GET raw .docx as an attachment."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Download document generation as docx'),
        operation_id=_('Download document generation'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.DOWNLOAD, target_type=FinanceAuditTargetType.DOC_GENERATION)
    def get(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        if not instance.output_oss_key:
            raise AppApiException(400, _('Generation has no rendered output yet'))
        docx_bytes = _load_bytes(instance.output_oss_key)
        # Resolve the template name for a friendly filename — fall back to the id.
        tpl = DocumentTemplate.objects.filter(id=instance.template_id).first()
        base_name = (tpl.name if tpl else str(instance.id)) or str(instance.id)
        filename = f'{base_name}.docx'
        response = HttpResponse(docx_bytes, content_type=_DOCX_MIME)
        # RFC 5987 — encode the filename so non-ASCII names survive.
        encoded = urllib.parse.quote(filename)
        response['Content-Disposition'] = (
            f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
        )
        return response


class DocumentGenerationAIFillView(APIView):
    """
    POST /generation/ai-fill — request AI-generated text for a subset of a
    template's placeholders.

    Gate 3 MVP — STUB IMPLEMENTATION.
    TODO(Gate 4): wire this to the workspace's default chat model. The plan
    is to load the FinanceProject's description + the template's
    placeholder metadata (label, ai_hint), build a system prompt, and call
    the chat-completion path used by ai_chat_step_node. For now we return
    a deterministic, recognisable placeholder so the UI flow can be built.
    """

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('AI-fill placeholders for a generation draft'),
        request=AIFillRequestSerializer,
        operation_id=_('AI-fill placeholders'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def post(self, request: Request, workspace_id):
        body = AIFillRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data

        template = DocumentTemplate.objects.filter(
            id=payload['template_id'], workspace_id=workspace_id, is_deleted=False
        ).first()
        if template is None:
            raise NotFound404(404, _('Template not found'))
        project = FinanceProject.objects.filter(
            id=payload['project_id'], workspace_id=workspace_id, is_deleted=False
        ).first()
        if project is None:
            raise NotFound404(404, _('Project not found'))

        filled = _do_ai_fill(
            template, project, payload['placeholder_keys'], workspace_id=str(workspace_id)
        )
        return result.success({'values': filled})

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
import os
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


def _async_enabled() -> bool:
    """Mirror of materials_task._async_enabled — Gate 7 Track B feature flag."""
    raw = (os.environ.get('FINANCE_ASYNC_ENABLED') or '').strip().lower()
    if raw in {'0', 'false', 'no', 'off'}:
        return False
    return True


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


# ---------------------------------------------------------------------------
# AI fill — batched single-call architecture
# ---------------------------------------------------------------------------
#
# **历史问题**：旧实现为每个占位符单独调一次 LLM（N 个字段 → N 次 chat_completion），
# 字段之间缺乏共享上下文（金额、报告日期、项目描述等在每次调用里都"独立想象"），
# 容易出现：字段一说"借款人 A 公司"、字段二说"A 集团"、字段三又编出别的名字 ——
# 各字段间相互矛盾，且严重浪费 token。
#
# **新方案**：把所有占位符 + 项目背景拼成一份 JSON-shaped 提示词，让模型一次返回
# 全部字段的 JSON。优点：
#   - 1 次 LLM 调用而非 N 次，延迟下降到 ~1/N，token 也省（共享上下文只算一次）。
#   - 模型在同一窗口内同时看到所有字段，前后文一致性大幅提高。
#   - 仍然 best-effort —— JSON 解析失败 / 字段缺失会回退到单字段 stub。
#
# **降级链**：批量解析失败 → 用旧的"每字段单独 stub"，永不抛异常。
# 单字段调用（aiFillOne）走的是同一函数，只是 placeholder_keys 长度 = 1。
# ---------------------------------------------------------------------------

_AI_FILL_BATCH_SYSTEM_PROMPT = (
    '你是合规融资文档撰写助手。下面给出一个融资项目的背景信息、相关材料概要和需要'
    '填写的占位符清单，请基于这些上下文，为**每个**占位符生成准确、专业、相互一致的内容。\n\n'
    '【项目背景】\n{project_block}\n\n'
    '{materials_block}'  # 整段（含标题 + 内容）由 _build_materials_block 生成；无材料时返回空串
    '【占位符清单（共 {n} 个）】\n{fields_block}\n\n'
    '【输出要求】\n'
    '1. 严格按 JSON 对象返回，key 是占位符 key（snake_case），value 是字符串内容；\n'
    '2. 所有列出的 key 都必须出现在 JSON 里，不要遗漏；\n'
    '3. 不要加任何 markdown 包装（不要 ```json fence）、不要解释、不要前后空行；\n'
    '4. 单个字段内容控制在 2000 字以内；数值/日期类字段返回字符串形式；\n'
    '5. 各字段在指代项目主体、金额、时间、行业等关键信息时必须保持一致；\n'
    '6. 如有相关材料概要，优先引用其事实数据，不要凭空编造。\n\n'
    '直接输出 JSON。'
)

# 单字段调用的轻量 prompt —— 没有"互相一致"约束，更便宜。
_AI_FILL_SINGLE_SYSTEM_PROMPT = (
    '你是合规融资文档撰写助手。请根据上下文，为下面这个占位符生成准确、专业的填充内容。\n'
    '  - 占位符标签：{label}\n'
    '  - 类型：{type}\n'
    '  - 提示：{ai_hint}\n'
    '  - 项目：{project_name} (代码 {project_code}, 金额 {target_amount} {currency})\n'
    '直接输出填充内容文本，不要加引号或额外说明。'
)


def _build_project_block(project: FinanceProject) -> str:
    """
    Format the project context as a bullet list for the batched prompt.

    Uses `getattr(..., default)` everywhere because the function is also
    called from unit tests that pass a SimpleNamespace fixture without the
    full FinanceProject field set — missing fields shouldn't tank the
    batched path.
    """
    name = getattr(project, 'name', '') or '（未命名项目）'
    code = getattr(project, 'code', '') or '（无）'
    project_type = getattr(project, 'project_type', '') or '（未指定）'
    target_amount = getattr(project, 'target_amount', None) or '（未指定）'
    currency = getattr(project, 'currency', '') or ''
    region = getattr(project, 'region', '') or '（未指定）'
    industry_code = getattr(project, 'industry_code', '') or '（未指定）'
    description = (getattr(project, 'description', '') or '').strip()

    lines = [
        f'  - 项目名称：{name}',
        f'  - 项目代码：{code}',
        f'  - 项目类型：{project_type}',
        f'  - 目标金额：{target_amount} {currency}',
        f'  - 地区：{region}',
        f'  - 行业代码：{industry_code}',
    ]
    if description:
        # 截断超长项目描述 —— 避免一项把 prompt 上下文吃满
        lines.append(f'  - 项目描述：{description[:800]}')
    return '\n'.join(lines)


def _build_fields_block(placeholders_meta: list[dict]) -> str:
    """Render the placeholder list as numbered lines with type + hint."""
    parts = []
    for i, meta in enumerate(placeholders_meta, 1):
        key = meta.get('key', '')
        label = meta.get('label') or key
        ph_type = meta.get('type') or 'text'
        ai_hint = (meta.get('ai_hint') or '').strip() or '无'
        parts.append(f'  {i}. {key} —— 标签：{label}，类型：{ph_type}，提示：{ai_hint}')
    return '\n'.join(parts)


# 单个材料概要在 prompt 里的硬上限 —— 防止一份超长概要把 context window 吃满。
_MATERIALS_SUMMARY_CHAR_BUDGET = 600
# 整个材料区段的总字符上限 —— 即便有 20 份材料也截到这里。
_MATERIALS_BLOCK_TOTAL_BUDGET = 6000


def _build_materials_block(project_id) -> str:
    """
    Aggregate AI summaries from the latest non-deleted MaterialsTask for
    `project_id`, formatted as a labelled block for the batched prompt.
    Returns '' when there's no usable materials data.

    Selection rule:
      - Only the **most recent** materials task per project (avoid stale
        summaries from earlier rounds bleeding in).
      - Within that task, only documents the user explicitly selected
        (`selected_documents`) — those are the ones the human curator
        actually wants in the package; everything else was tentative.
      - Skip rows without an `ai_summary` or with a fallback-marker
        summary; those add noise without value.

    Best-effort: any DB / model failure returns ''. Never raises.
    """
    if not project_id:
        return ''
    try:
        # Late import keeps this function callable from unit tests that
        # don't bootstrap the full Django app graph.
        from finance.models import MaterialsTask
    except Exception:  # noqa: BLE001
        return ''

    try:
        task = (
            MaterialsTask.objects
            .filter(project_id=project_id, is_deleted=False)
            .exclude(matched_documents=[])
            .order_by('-created_at')
            .first()
        )
    except Exception as e:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.ai_fill] materials lookup failed: {e}')
        return ''
    if task is None:
        return ''

    selected = {str(s) for s in (task.selected_documents or [])}
    rows: list[str] = []
    used_chars = 0
    for row in task.matched_documents or []:
        if not isinstance(row, dict):
            continue
        doc_id = row.get('document_id')
        summary = (row.get('ai_summary') or '').strip()
        if not summary or summary.startswith('[AI 概要：'):
            continue  # skip placeholder stubs
        # 只取用户最终选中的文档 —— 没选的属于"候选 noise"
        if selected and (doc_id is None or str(doc_id) not in selected):
            continue
        doc_name = (row.get('document_name') or '').strip() or '（未命名文档）'
        snippet = summary[:_MATERIALS_SUMMARY_CHAR_BUDGET]
        line = f'  - 《{doc_name}》：{snippet}'
        if used_chars + len(line) > _MATERIALS_BLOCK_TOTAL_BUDGET:
            rows.append('  - …（更多材料概要已省略，超出 prompt 上下文配额）')
            break
        rows.append(line)
        used_chars += len(line)

    if not rows:
        return ''
    return (
        f'【相关材料概要（来自材料任务：{task.title}）】\n'
        + '\n'.join(rows)
        + '\n\n'
    )


def _parse_batch_response(text: str, wanted_keys: set) -> dict:
    """
    Try to extract a {key: value} dict from the model's JSON response.
    Handles common drift: ```json fences, leading/trailing prose, surrounding
    backticks. Returns {} on any failure — caller falls back to stubs.
    """
    import json as _json
    import re as _re

    if not text:
        return {}
    cleaned = text.strip()
    # 剥 ```json fence（模型偶尔无视指令）
    fence = _re.match(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', cleaned, flags=_re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    # 找到第一个 `{` 和最后一个 `}` —— 兼容前后有解释文字
    start, end = cleaned.find('{'), cleaned.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        obj = _json.loads(cleaned[start:end + 1])
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(obj, dict):
        return {}
    # 只保留我们 ask 过的 key，且 value 必须是字符串-able
    result: dict = {}
    for k in wanted_keys:
        v = obj.get(k)
        if v is None:
            continue
        if isinstance(v, (str, int, float)):
            result[k] = str(v)
        elif isinstance(v, list):
            # 偶尔模型会返回数组（"多个值"）—— 拼回字符串
            result[k] = '\n'.join(str(x) for x in v)
        # 其他类型（dict/None）跳过 → fallback 到 stub
    return result


def _do_ai_fill(template: DocumentTemplate, project: FinanceProject,
                placeholder_keys, workspace_id: str = 'default') -> dict:
    """
    Generate AI-filled values for the requested placeholder keys.

    Strategy:
      1. **Batched**: pack all wanted placeholders + project context into a
         single prompt asking for JSON. Parse the response and accept every
         well-formed entry.
      2. **Per-key fallback**: any key the batched call didn't deliver
         (parse error, model omitted it, oversized) gets a single-field
         LLM retry with the legacy prompt.
      3. **Stub fallback**: anything still missing returns `[AI 待生成: <label>]`
         so the UI can flag it.

    The function MUST NOT raise. Unknown keys (not in template.placeholders)
    are silently dropped from the result.
    """
    wanted = set(placeholder_keys)
    placeholders_by_key = {p.get('key'): p for p in (template.placeholders or [])}
    # 过滤出真正存在于模板里的 key —— 既排重又防御注入
    valid_meta = [placeholders_by_key[k] for k in wanted if k in placeholders_by_key]
    valid_keys = {m.get('key') for m in valid_meta}
    if not valid_meta:
        return {}

    # 单字段响应硬上限 —— 防失控模型把 docx 渲染撑爆
    max_chars = 2048
    filled: dict = {}

    # ---- 1. 批量 JSON 调用 ----
    try:
        # 材料概要：同一项目下最近一次材料任务里、用户选中的文档的 ai_summary。
        # 找不到就返回空串，prompt 模板里那段就自然退化为空段不影响结构。
        materials_block = _build_materials_block(getattr(project, 'id', None))
        system_prompt = _AI_FILL_BATCH_SYSTEM_PROMPT.format(
            project_block=_build_project_block(project),
            materials_block=materials_block,
            fields_block=_build_fields_block(valid_meta),
            n=len(valid_meta),
        )
        text = chat_completion(workspace_id, system_prompt, '请按 JSON 返回。')
        batched = _parse_batch_response(text or '', valid_keys)
        for k, v in batched.items():
            content = v.strip()
            if content and len(content) <= max_chars:
                filled[k] = content
    except Exception as e:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.ai_fill] batched call failed, will fallback per-key: {e}')

    # ---- 2. 单字段补漏 ----
    missing_after_batch = [m for m in valid_meta if m.get('key') not in filled]
    for meta in missing_after_batch:
        key = meta.get('key')
        label = meta.get('label') or key
        ph_type = meta.get('type') or 'text'
        ai_hint = meta.get('ai_hint') or '无'
        stub = f'[AI 待生成: {label}]'
        try:
            single_prompt = _AI_FILL_SINGLE_SYSTEM_PROMPT.format(
                label=label, type=ph_type, ai_hint=ai_hint,
                project_name=project.name, project_code=project.code or '',
                target_amount=project.target_amount, currency=project.currency,
            )
            text = chat_completion(workspace_id, single_prompt, '请生成内容。')
            content = (text or '').strip()
            if content and len(content) <= max_chars:
                filled[key] = content
            else:
                filled[key] = stub
        except Exception as e:  # noqa: BLE001
            maxkb_logger.warning(f'[finance.ai_fill] per-key retry failed for {key}: {e}')
            filled[key] = stub

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
        # Gate 7 Track B: hand off to Celery so the HTTP request returns
        # immediately. The row stays in status=GENERATING until the worker
        # promotes it to PENDING_REVIEW (or FAILED). Frontend polls via
        # the existing detail endpoint.
        if _async_enabled():
            from finance.service.workflow_runtime import create_queued_run
            from finance.tasks import async_generate

            wr = create_queued_run(
                workspace_id=workspace_id,
                target_type='DOC_GENERATION',
                target_id=gen.id,
                task_name='finance.documents.async_generate',
                payload={
                    'workspace_id': str(workspace_id),
                    'template_id': str(template.id),
                    'project_id': str(project.id),
                },
            )
            if wr is not None:
                gen.workflow_run_id = wr.id
                gen.save(update_fields=['workflow_run_id', 'updated_at'])
            async_generate.delay(str(gen.id), run_id=str(wr.id) if wr else None)
        else:
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
        # Contract: return the filled map directly (``{<key>: <text>}``). An
        # earlier version wrapped this in ``{'values': filled}`` which
        # silently broke the front-end — every key was ``undefined`` on
        # lookup, so the textarea stayed empty and the user saw "no
        # response" despite a 200. Direct map matches AIFillResponse type
        # in ui/src/api/finance/type.ts and the existing store contract.
        return result.success(filled)

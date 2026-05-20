# coding=utf-8
"""
@project: MaxKB
@file： document_template.py
@desc: DocumentTemplate REST endpoints. Permissions mirror project.py:
  - FINANCE_READ for list/detail
  - FINANCE_TEMPLATE_MANAGE for upload/update/delete
  - WORKSPACE_MANAGE roles fall through for management ops.
"""

from django.db.models import Q
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
from django.http import HttpResponse
import urllib.parse

from finance.models import DocumentTemplate, FinanceAuditAction, FinanceAuditTargetType
from finance.serializers.document_template import (
    DocumentTemplateOutputSerializer,
    DocumentTemplateUpdateSerializer,
    DocumentTemplateUploadSerializer,
)
from finance.service.audit import audit_log
from finance.service.document_generator import (
    build_sample_template_bytes,
    load_template_bytes,
    store_template_bytes,
)
from finance.service.template_annotation import suggest_placeholder_annotations
from finance.service.template_parser import extract_plain_text, extract_placeholders


def _docx_attachment_response(docx_bytes: bytes, filename: str) -> HttpResponse:
    """Build a standard ``Content-Disposition: attachment`` response for a .docx body."""
    response = HttpResponse(docx_bytes, content_type=_DOCX_MIME)
    encoded = urllib.parse.quote(filename)
    # RFC 5987 — keep non-ASCII filenames intact across browsers.
    response["Content-Disposition"] = f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
    return response


_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _parse_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _paginate(queryset, query_params):
    page = _parse_int(query_params.get("page"), _DEFAULT_PAGE)
    size = min(_parse_int(query_params.get("size"), _DEFAULT_SIZE), _MAX_SIZE)
    total = queryset.count()
    offset = (page - 1) * size
    records = list(queryset[offset : offset + size])
    return total, page, size, records


def _validate_docx_upload(uploaded):
    """Reject anything that's clearly not a .docx upload."""
    if uploaded is None:
        raise AppApiException(400, _("Missing template file"))
    name = (getattr(uploaded, "name", "") or "").lower()
    if not name.endswith(".docx"):
        raise AppApiException(400, _("Template file must be a .docx"))
    content_type = getattr(uploaded, "content_type", "") or ""
    # Some browsers send octet-stream — allow that as long as extension matches.
    if content_type and content_type not in (_DOCX_MIME, "application/octet-stream"):
        raise AppApiException(400, _("Template file must be a .docx"))


class DocumentTemplateListView(APIView):
    """GET (list) + POST (upload + auto-extract placeholders)."""

    authentication_classes = [TokenAuth]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        methods=["GET"],
        summary=_("List document templates"),
        operation_id=_("List document templates"),  # type: ignore
        tags=[_("Finance")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = DocumentTemplate.objects.filter(workspace_id=workspace_id, is_deleted=False)
        scenario = (request.query_params.get("scenario") or "").strip()
        if scenario:
            qs = qs.filter(scenario=scenario)
        keyword = (request.query_params.get("keyword") or "").strip()
        if keyword:
            qs = qs.filter(Q(name__icontains=keyword))
        total, page, size, records = _paginate(qs, request.query_params)
        serializer = DocumentTemplateOutputSerializer(records, many=True)
        return result.success(result.Page(total=total, records=serializer.data, current_page=page, page_size=size))

    @extend_schema(
        methods=["POST"],
        summary=_("Upload document template"),
        request=DocumentTemplateUploadSerializer,
        responses=DocumentTemplateOutputSerializer,
        tags=[_("Finance")],  # type: ignore
        operation_id=_("Upload document template"),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_TEMPLATE_MANAGE.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.CREATE, target_type=FinanceAuditTargetType.DOC_TEMPLATE)
    def post(self, request: Request, workspace_id):
        body = DocumentTemplateUploadSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        uploaded = payload["file"]
        _validate_docx_upload(uploaded)

        file_bytes = uploaded.read()
        try:
            placeholders = extract_placeholders(file_bytes)
        except Exception as e:  # noqa: BLE001
            # docxtpl raises on malformed Jinja syntax — bubble up as 400.
            raise AppApiException(400, _("Failed to parse template: %s") % str(e)) from e

        oss_key = store_template_bytes(file_bytes, uploaded.name)
        tpl = DocumentTemplate.objects.create(
            workspace_id=workspace_id,
            name=payload["name"],
            scenario=payload["scenario"],
            docx_oss_key=oss_key,
            placeholders=placeholders,
            version=1,
            is_active=True,
            created_by=request.user.id,
        )
        return result.success(DocumentTemplateOutputSerializer(tpl).data)


class DocumentTemplateDetailView(APIView):
    """GET (detail) + PUT (metadata-only update) + DELETE (soft)."""

    authentication_classes = [TokenAuth]

    @staticmethod
    def _get_or_404(workspace_id, pk):
        instance = DocumentTemplate.objects.filter(id=pk, workspace_id=workspace_id, is_deleted=False).first()
        if instance is None:
            raise NotFound404(404, _("Template not found"))
        return instance

    @extend_schema(
        methods=["GET"],
        summary=_("Get document template"),
        operation_id=_("Get document template"),  # type: ignore
        tags=[_("Finance")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id, pk):
        instance = self._get_or_404(workspace_id, pk)
        return result.success(DocumentTemplateOutputSerializer(instance).data)

    @extend_schema(
        methods=["PUT"],
        summary=_("Update document template"),
        request=DocumentTemplateUpdateSerializer,
        responses=DocumentTemplateOutputSerializer,
        tags=[_("Finance")],  # type: ignore
        operation_id=_("Update document template"),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_TEMPLATE_MANAGE.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.DOC_TEMPLATE)
    def put(self, request: Request, workspace_id, pk):
        instance = self._get_or_404(workspace_id, pk)
        body = DocumentTemplateUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data

        updates = []
        if "name" in payload:
            instance.name = payload["name"]
            updates.append("name")
        if "scenario" in payload:
            instance.scenario = payload["scenario"]
            updates.append("scenario")
        if "is_active" in payload:
            instance.is_active = payload["is_active"]
            updates.append("is_active")
        if "placeholders" in payload:
            # Trust the serializer's nested validator — list of dicts.
            instance.placeholders = list(payload["placeholders"])
            updates.append("placeholders")

        if updates:
            updates.append("updated_at")
            instance.save(update_fields=updates)
        return result.success(DocumentTemplateOutputSerializer(instance).data)

    @extend_schema(
        methods=["DELETE"],
        summary=_("Delete document template"),
        operation_id=_("Delete document template"),  # type: ignore
        tags=[_("Finance")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_TEMPLATE_MANAGE.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.DELETE, target_type=FinanceAuditTargetType.DOC_TEMPLATE)
    def delete(self, request: Request, workspace_id, pk):
        instance = self._get_or_404(workspace_id, pk)
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])
        return result.success({"id": str(instance.id)})


class DocumentTemplatePlaceholderSuggestView(APIView):
    """POST: generate editable placeholder label / AI-hint suggestions."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=["POST"],
        summary=_("Suggest document template placeholder metadata"),
        responses=DocumentTemplateOutputSerializer,
        tags=[_("Finance")],  # type: ignore
        operation_id=_("Suggest document template placeholder metadata"),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_TEMPLATE_MANAGE.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def post(self, request: Request, workspace_id, pk):  # noqa: ARG002
        instance = DocumentTemplateDetailView._get_or_404(workspace_id, pk)
        template_text = ""
        parsed_by_key = {}
        try:
            docx_bytes = load_template_bytes(instance.docx_oss_key)
            template_text = extract_plain_text(docx_bytes)
            parsed_by_key = {p["key"]: p for p in extract_placeholders(docx_bytes)}
        except Exception:  # noqa: BLE001
            # Best-effort: even if the original file is unavailable, the saved
            # JSON metadata is enough for local key-based suggestions.
            parsed_by_key = {}

        placeholders = []
        for item in instance.placeholders or []:
            key = item.get("key")
            if not key:
                continue
            parsed = parsed_by_key.get(key, {})
            placeholders.append(
                {
                    "key": key,
                    "label": parsed.get("label") or item.get("label") or key,
                    "type": item.get("type") or parsed.get("type") or "text",
                    "required": False,
                    "ai_hint": parsed.get("ai_hint") or item.get("ai_hint") or "",
                    "enum_options": item.get("enum_options") or parsed.get("enum_options") or [],
                }
            )

        suggested = suggest_placeholder_annotations(
            placeholders,
            workspace_id=workspace_id,
            template_name=instance.name,
            template_text=template_text,
        )
        return result.success({"placeholders": suggested})


class DocumentTemplateSampleView(APIView):
    """
    GET a freshly generated sample .docx demonstrating placeholder syntax.

    No template id required — built on the fly from python-docx so it always
    reflects the current placeholder/type contract. Auth: workspace member.
    """

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=["GET"],
        summary=_("Download sample document template"),
        operation_id=_("Download sample document template"),  # type: ignore
        tags=[_("Finance")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):  # noqa: ARG002 — workspace_id reserved for future per-ws templates
        docx_bytes = build_sample_template_bytes()
        return _docx_attachment_response(docx_bytes, "finance-template-sample.docx")


class DocumentTemplateDownloadView(APIView):
    """
    GET the previously uploaded template's raw .docx so users can download,
    edit (e.g. tweak placeholders), and upload again as a new template
    (or replace once that endpoint exists).
    """

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=["GET"],
        summary=_("Download uploaded document template"),
        operation_id=_("Download uploaded document template"),  # type: ignore
        tags=[_("Finance")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.DOWNLOAD, target_type=FinanceAuditTargetType.DOC_TEMPLATE)
    def get(self, request: Request, workspace_id, pk):
        instance = DocumentTemplate.objects.filter(id=pk, workspace_id=workspace_id, is_deleted=False).first()
        if instance is None:
            raise NotFound404(404, _("Template not found"))
        try:
            docx_bytes = load_template_bytes(instance.docx_oss_key)
        except ValueError as e:
            raise AppApiException(500, _("Template file missing in storage: %s") % str(e)) from e
        filename = f"{instance.name or str(instance.id)}.docx"
        return _docx_attachment_response(docx_bytes, filename)

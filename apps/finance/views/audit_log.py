# coding=utf-8
"""
    @project: MaxKB
    @file： audit_log.py
    @desc: Read-only list view for FinanceAuditLog (Gate 5 Track C).

    This is an admin/compliance surface — it is NOT the same as the
    individual-object audit tabs that surface inside each resource's detail
    page. The endpoint is workspace-scoped because finance audit rows
    themselves are workspace-scoped (see FinanceAuditLog.workspace_id);
    cross-workspace audit views would be a system-level concern handled
    elsewhere.

    Permission contract:
        - Reads require either FINANCE_REVIEW (compliance reviewer role)
          OR WORKSPACE_MANAGE (workspace admin). The route is NOT gated on
          plain FINANCE_READ so day-to-day finance staff cannot see who
          read what.
        - There is no write path — the table is append-only via the
          ``audit_log`` decorator + ``log_event`` helper.

    Query parameters (all optional):
        - target_type   one of FinanceAuditTargetType
        - action        one of FinanceAuditAction
        - actor_id      UUID of the actor user
        - target_id     UUID of the audited row
        - date_from     ISO-8601 (inclusive lower bound on created_at)
        - date_to       ISO-8601 (exclusive upper bound on created_at)
        - keyword       substring match on the JSON payload (path field)
        - page, size    pagination
"""
import csv
import io
import json
from datetime import datetime, timezone

from django.db.models import Q
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.dateparse import parse_datetime
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from finance.models import FinanceAuditAction, FinanceAuditLog, FinanceAuditTargetType
from finance.serializers.audit_log import FinanceAuditLogOutputSerializer
from finance.service.audit import audit_log

_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200

_VALID_TARGET_TYPES = {choice for choice, _label in FinanceAuditTargetType.choices}
_VALID_ACTIONS = {choice for choice, _label in FinanceAuditAction.choices}


def _parse_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        return parse_datetime(str(value))
    except (TypeError, ValueError):
        return None


def _build_queryset(workspace_id, query_params):
    """
    Build a filtered FinanceAuditLog queryset.

    Unknown enum filter values are silently dropped (rather than raising),
    matching the convention used by FinanceProjectListView — the audit page
    is meant to feel forgiving when operators paste partial filters from
    URL bars.
    """
    qs = FinanceAuditLog.objects.filter(workspace_id=workspace_id)

    target_type = (query_params.get('target_type') or '').strip()
    if target_type and target_type in _VALID_TARGET_TYPES:
        qs = qs.filter(target_type=target_type)

    action = (query_params.get('action') or '').strip()
    if action and action in _VALID_ACTIONS:
        qs = qs.filter(action=action)

    actor_id = (query_params.get('actor_id') or '').strip()
    if actor_id:
        # Let an invalid UUID quietly miss rather than 500: ORM will still
        # accept the string for an indexed UUID field on PostgreSQL and
        # simply return no matches.
        qs = qs.filter(actor_id=actor_id)

    target_id = (query_params.get('target_id') or '').strip()
    if target_id:
        qs = qs.filter(target_id=target_id)

    date_from = _parse_iso(query_params.get('date_from'))
    if date_from is not None:
        qs = qs.filter(created_at__gte=date_from)
    date_to = _parse_iso(query_params.get('date_to'))
    if date_to is not None:
        qs = qs.filter(created_at__lt=date_to)

    keyword = (query_params.get('keyword') or '').strip()
    if keyword:
        # PostgreSQL JSONField casts to text for icontains — handy for the
        # path/method snapshot we store. Limit to a sensible cap so a stray
        # keyword doesn't kill the index.
        if len(keyword) <= 128:
            qs = qs.filter(Q(payload__icontains=keyword) | Q(user_agent__icontains=keyword))

    return qs.order_by('-created_at')


def _paginate(queryset, query_params):
    page = _parse_int(query_params.get('page'), _DEFAULT_PAGE)
    size = _parse_int(query_params.get('size'), _DEFAULT_SIZE)
    size = min(size, _MAX_SIZE)
    total = queryset.count()
    offset = (page - 1) * size
    records = list(queryset[offset: offset + size])
    return total, page, size, records


class FinanceAuditLogListView(APIView):
    """
    GET /finance/workspace/<workspace_id>/audit-log

    Lists audit rows for one workspace, newest first, with the filter set
    described in the module docstring. There is intentionally no detail
    view: a single row's ``payload`` is already returned inline and the
    list view is the only read surface clients need.
    """

    authentication_classes = [TokenAuth]

    @has_permissions(
        # OR semantics by default — reviewer permission OR workspace-admin
        # role is sufficient. Audit log is intentionally NOT gated on plain
        # FINANCE_READ so day-to-day finance staff can't observe each
        # other's clicks.
        PermissionConstants.FINANCE_REVIEW.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = _build_queryset(workspace_id, request.query_params)
        total, page, size, records = _paginate(qs, request.query_params)
        serializer = FinanceAuditLogOutputSerializer(records, many=True)
        return result.success(result.Page(
            total=total,
            records=serializer.data,
            current_page=page,
            page_size=size,
        ))


# ---- Gate 6 Track A4: audit log CSV export ----

_EXPORT_MAX_ROWS = 50_000
_EXPORT_CHUNK = 500  # iterator chunk size for the queryset

# Column headers — bilingual labels so compliance reviewers reading the
# CSV in Excel get the Chinese label they expect, while the underlying
# data is the raw enum/UUID value (not the i18n label) so cross-tool
# correlation stays trivial.
_CSV_HEADERS = [
    '时间 (created_at)',
    '操作人ID (actor_id)',
    '操作 (action)',
    '对象类型 (target_type)',
    '对象ID (target_id)',
    'IP',
    'User-Agent',
    'Payload (JSON)',
]


def _iter_csv_rows(queryset):
    """
    Yield CSV byte chunks for a streamed response.

    Uses ``queryset.iterator(chunk_size=...)`` so we don't materialise
    the entire result set in memory; the 50K row cap is enforced
    against the limited queryset rather than the raw count, so a
    matching set of 1M rows simply truncates at 50K instead of OOM-ing
    the worker.
    """
    # csv writes text; we wrap a per-chunk StringIO so each yield is a
    # finalised, encoded byte string (suitable for StreamingHttpResponse).
    def _flush(buf: io.StringIO) -> bytes:
        # UTF-8 BOM is prepended on the first row by the caller so Excel
        # opens the file in the right encoding without manual import.
        data = buf.getvalue().encode('utf-8')
        buf.seek(0)
        buf.truncate(0)
        return data

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)

    # BOM helps Excel auto-detect UTF-8.
    yield '﻿'.encode('utf-8')

    writer.writerow(_CSV_HEADERS)
    yield _flush(buf)

    for row in queryset.iterator(chunk_size=_EXPORT_CHUNK):
        # ``payload`` is a JSONField — serialise inline with ensure_ascii=False
        # so Chinese strings render correctly in the CSV cell.
        try:
            payload_json = json.dumps(row.payload or {}, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            payload_json = ''
        writer.writerow([
            row.created_at.isoformat() if row.created_at else '',
            str(row.actor_id) if row.actor_id else '',
            row.action or '',
            row.target_type or '',
            str(row.target_id) if row.target_id else '',
            row.ip or '',
            (row.user_agent or '')[:512],
            payload_json,
        ])
        yield _flush(buf)


def _filename_for_export(workspace_id: str, ext: str = 'csv') -> str:
    """``finance_audit_<workspace>_<utc-stamp>.<ext>``"""
    stamp = datetime.now(tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    safe_ws = ''.join(c for c in str(workspace_id) if c.isalnum() or c in ('-', '_'))[:32]
    safe_ext = ext if ext in ('csv', 'xlsx') else 'csv'
    return f'finance_audit_{safe_ws or "default"}_{stamp}.{safe_ext}'


# ---- Gate 7 Track A2: xlsx export -----------------------------------------
#
# Build an xlsx workbook in-memory (openpyxl is fully in-memory anyway) and
# return as a single HttpResponse rather than streaming — openpyxl's writer
# doesn't expose a chunk-by-chunk iterator without the optional ``write_only``
# mode, and a 50K-row sheet is well under what an in-memory workbook can hold.

_XLSX_HEADER_LABELS = _CSV_HEADERS  # identical bilingual labels — keep parity
_XLSX_SHEET_NAME = 'finance_audit'
_XLSX_PAYLOAD_COL_WIDTH = 80
_XLSX_DEFAULT_COL_WIDTH = 22
_XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)


def _build_xlsx_bytes(queryset) -> bytes:
    """
    Build an xlsx file from the queryset and return its raw bytes.

    Uses ``write_only`` mode so rows are streamed to the underlying
    zipfile rather than retained in memory — important for the 50K
    row cap. The header row uses ``Font(bold=True)`` and the payload
    column is wrapped + capped at 80 chars wide so reviewers don't
    end up with a single column hogging their screen.
    """
    # Lazy import keeps openpyxl off the import graph for non-export
    # requests — the dep is heavy and we don't want to pay for it on
    # every audit-log list call.
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title=_XLSX_SHEET_NAME)

    # Header row — bold. In write_only mode we have to use WriteOnlyCell
    # because styled cells can't be passed as plain values.
    from openpyxl.cell import WriteOnlyCell

    header_cells = []
    bold = Font(bold=True)
    for label in _XLSX_HEADER_LABELS:
        cell = WriteOnlyCell(ws, value=label)
        cell.font = bold
        header_cells.append(cell)
    ws.append(header_cells)

    # Column widths. In write_only mode column dimensions are still
    # writable before we save.
    for idx, _ in enumerate(_XLSX_HEADER_LABELS, start=1):
        letter = get_column_letter(idx)
        # Last column (payload) wider + wrapped.
        if idx == len(_XLSX_HEADER_LABELS):
            ws.column_dimensions[letter].width = _XLSX_PAYLOAD_COL_WIDTH
        else:
            ws.column_dimensions[letter].width = _XLSX_DEFAULT_COL_WIDTH

    payload_alignment = Alignment(wrap_text=True, vertical='top')

    for row in queryset.iterator(chunk_size=_EXPORT_CHUNK):
        try:
            payload_json = json.dumps(row.payload or {}, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            payload_json = ''

        cells = [
            row.created_at.isoformat() if row.created_at else '',
            str(row.actor_id) if row.actor_id else '',
            row.action or '',
            row.target_type or '',
            str(row.target_id) if row.target_id else '',
            row.ip or '',
            (row.user_agent or '')[:512],
        ]
        # Wrap the payload column explicitly.
        payload_cell = WriteOnlyCell(ws, value=payload_json)
        payload_cell.alignment = payload_alignment
        cells.append(payload_cell)
        ws.append(cells)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


class FinanceAuditLogExportView(APIView):
    """
    GET /finance/workspace/<workspace_id>/audit-log/export

    Streams up to ``_EXPORT_MAX_ROWS`` (50,000) matching rows as a CSV
    attachment. Accepts the same query filters as the list endpoint
    (target_type, action, actor_id, target_id, date_from, date_to,
    keyword). Permission contract matches the list view: FINANCE_REVIEW
    permission OR WORKSPACE_MANAGE role.

    The export itself is audited (action=DOWNLOAD, target_type=OTHER)
    via the ``@audit_log`` decorator — the audit table records every
    bulk read of itself, which compliance reviewers expect.

    Format support:
        ?format=csv   (default; streamed, UTF-8 BOM for Excel)
        ?format=xlsx  (Gate 7 A2 — bold header, wrapped payload column,
                      same 50K row cap, returned as single in-memory
                      response)
    """

    authentication_classes = [TokenAuth]

    @has_permissions(
        PermissionConstants.FINANCE_REVIEW.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(
        action=FinanceAuditAction.DOWNLOAD,
        target_type=FinanceAuditTargetType.OTHER,
    )
    def get(self, request: Request, workspace_id):
        fmt = (request.query_params.get('format') or 'csv').strip().lower()
        if fmt not in ('csv', 'xlsx'):
            from common.exception.app_exception import AppApiException
            raise AppApiException(
                400,
                f"format={fmt!r} is not supported; expected 'csv' or 'xlsx'",
            )

        qs = _build_queryset(workspace_id, request.query_params)
        # Slice at the export cap. Note: Django evaluates [:N] lazily,
        # so this still streams via ``iterator()`` below (for CSV) or
        # iterates row-by-row into the workbook (for xlsx).
        qs = qs[:_EXPORT_MAX_ROWS]

        if fmt == 'xlsx':
            filename = _filename_for_export(workspace_id, ext='xlsx')
            payload = _build_xlsx_bytes(qs)
            response = HttpResponse(
                payload,
                content_type=_XLSX_CONTENT_TYPE,
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = str(len(payload))
            return response

        filename = _filename_for_export(workspace_id, ext='csv')
        response = StreamingHttpResponse(
            _iter_csv_rows(qs),
            content_type='text/csv; charset=utf-8',
        )
        # ``attachment`` forces a download dialog; the filename is
        # ASCII-safe (workspace ids are alnum/dash/underscore-stripped).
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        # No length header — streamed response.
        return response

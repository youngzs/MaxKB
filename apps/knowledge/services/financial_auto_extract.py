# coding=utf-8
"""
@project: maxkb
@file: financial_auto_extract.py
@desc: 批量上传 hook —— 对 doc_type=财务报表 标签的文档，扫描其段落里的
       markdown 表格，自动落 FinancialStatement / FinancialFact。

设计：
  - 与 auto_tag_documents 一样在 batch_save 末尾跑；失败不阻断主流程。
  - 复用 Paragraph.content 文本（split 时表格已经被表格感知分块），从中抠出
    每个 "| --- |" 形式的 markdown 表格喂给 extractor。
  - extractor 对非财务表格返回 None，直接跳过 —— 无副作用。
"""

import re
from typing import Iterable, List

from django.db import transaction
from django.db.models import QuerySet

from knowledge.models import Document, DocumentTag, Paragraph, Tag
from knowledge.services.financial_extractor import parse_document, parse_table, persist

_TABLE_BLOCK_RE = re.compile(
    # 至少一个 markdown 表格行 + 分隔行 + 数据行
    r"(\|[^\n]+\|\s*\n\|\s*[:\-\s|]+\|\s*\n(?:\|[^\n]+\|\s*\n?)+)",
    re.MULTILINE,
)


def _strip_seq_prefix(name: str) -> str:
    """去掉目录段常见的'数字、'/'数字.'前缀，如 '5、沛县千岛...' → '沛县千岛...'。"""
    return re.sub(r"^\s*\d+\s*[、.\)）]\s*", "", name or "").strip()


def _detect_default_entity(document: Document) -> str:
    """从 Document.meta.path_segments 兜底推断主体名（公司名通常是最靠前的目录段）。
    注意：模板感知解析会优先用表格里的'编制单位：'，这里只是兜底。"""
    meta = document.meta or {}
    segs = meta.get("path_segments") or []
    if isinstance(segs, list) and segs:
        # 取第一个像公司名的段（含'公司/有限/集团/中心/厂'），否则取首段
        for seg in segs:
            s = _strip_seq_prefix(seg)
            if any(kw in s for kw in ("公司", "有限", "集团", "中心", "厂", "事务所", "医院", "学校")):
                return s
        return _strip_seq_prefix(segs[0])
    return ""


def _detect_filename(document: Document) -> str:
    """报表源文件名（path_segments 最后一段），用于年度兜底推断。"""
    meta = document.meta or {}
    segs = meta.get("path_segments") or []
    if isinstance(segs, list) and segs:
        return segs[-1] or ""
    return document.name or ""


def _ordered_paragraph_contents(document_id) -> List[str]:
    return [
        c
        for c in QuerySet(Paragraph)
        .filter(document_id=document_id)
        .order_by("position")
        .values_list("content", flat=True)
        if c
    ]


def _has_financial_report_tag(knowledge_id, document_id) -> bool:
    """该文档是否带 doc_type=财务报表 / 审计报告 标签。"""
    tag_ids = list(
        QuerySet(Tag)
        .filter(
            knowledge_id=knowledge_id,
            key="doc_type",
            value__in=["财务报表", "审计报告"],
        )
        .values_list("id", flat=True)
    )
    if not tag_ids:
        return False
    return QuerySet(DocumentTag).filter(document_id=document_id, tag_id__in=tag_ids).exists()


def _extract_tables_from_paragraphs(document_id) -> List[str]:
    """把该文档所有段落 content 拼起来，按表格 fence 切出 markdown 表格块。"""
    contents = list(QuerySet(Paragraph).filter(document_id=document_id).values_list("content", flat=True))
    if not contents:
        return []
    blob = "\n\n".join(c for c in contents if c)
    return _TABLE_BLOCK_RE.findall(blob)


def auto_extract_financial(knowledge_id, documents: Iterable[Document]) -> int:
    """对带"财务报表"标签的文档跑抽取；返回抽取出的 statement 数。
    任何单文档失败都吞掉异常，继续下一个 —— 抽取是增强能力，不能阻挡上传。"""
    stmt_count = 0
    for doc in documents:
        if not doc or not doc.id:
            continue
        try:
            # 每文档一个 savepoint：抽取写库失败只回滚自身，不毒化外层 batch_save 上传事务
            with transaction.atomic():
                if not _has_financial_report_tag(knowledge_id, doc.id):
                    continue
                entity = _detect_default_entity(doc)
                # —— 首选：文档级模板感知解析（国产财务软件导出的双栏+财务指标报表，
                #     表头/期间/指标块常被分块打散，需整篇一起看）。
                contents = _ordered_paragraph_contents(doc.id)
                parsed_doc = (
                    parse_document(contents, doc_name=doc.name, filename=_detect_filename(doc), default_entity=entity)
                    if contents
                    else None
                )
                if parsed_doc is not None:
                    created, _facts = persist(doc, parsed_doc, raw_table_md="\n\n".join(contents))
                    stmt_count += len(created)
                    continue
                # —— 回退：旧的逐表格解析（兼容非该模板的报表）。
                md_tables = _extract_tables_from_paragraphs(doc.id)
                if not md_tables:
                    continue
                for md in md_tables:
                    parsed = parse_table(md, default_entity=entity)
                    if parsed is None:
                        continue
                    created, _facts = persist(doc, parsed, raw_table_md=md)
                    stmt_count += len(created)
        except Exception:
            # 单文档失败 → 跳过；外层 batch_save 永远成功
            continue
    return stmt_count

# coding=utf-8
"""
@project: maxkb
@file: retrieval_enrich.py
@desc: 检索增强（上传管线 productize）——两件事，均为"增强能力、失败不阻断上传"：

A. 上下文标签注入 inject_context_titles：
   给文档每个段落的 title 前缀 `【公司名｜类别｜期间｜文档类型】`。
   因 MaxKB 嵌入文本 = concat_ws('\\n', paragraph.title, paragraph.content)
   （见 apps/common/sql/list_embedding_text.sql），把判别性元数据写进 title
   即可提升召回（原生 doc_type/path 标签不进向量，故必须写 title）。
   在 batch_save 内、段落 bulk_create 之后调用；随后的 post_embedding 会嵌入
   带标签的 title，无需重嵌入。

B. 财务指标摘要回写 writeback_financial_summary：
   从 FinancialStatement/FinancialFact（auto_extract_financial 产出）按 entity_name
   聚合各年 资产总计/负债总计/所有者权益/营收/净利润 + 算资产负债率，生成一条
   "历年财务指标"合并段落写进【该公司同名知识库】并嵌入，使 chat-entry 能直接
   答出财务比率（不依赖 LLM 现场抠原始乱表）。

两个总开关可分别一键回退。
"""

import re
from typing import Iterable

from django.db import transaction
from django.db.models import QuerySet

from common.config.embedding_config import VectorStore
from common.utils.logger import maxkb_logger
from knowledge.models import Document, Paragraph, Knowledge, Tag, DocumentTag, FinancialStatement, FinancialFact
from knowledge.task.embedding import embedding_by_paragraph

CONTEXT_TAG_ENABLED = True  # A 档总开关：上下文标签注入 title
FIN_SUMMARY_ENABLED = True  # B 档总开关：财务指标摘要回写
SUMMARY_DOC_NAME = "财务指标摘要（系统生成）"

# 文件名关键词 → (类别, 文档类型) 兜底（doc_type 标签缺失时用），顺序敏感（先具体后宽泛）
_NAME_PAIRS = [
    ("资产负债表", "财务", "资产负债表"),
    ("利润", "财务", "利润表"),
    ("现金流量", "财务", "现金流量表"),
    ("科目明细", "财务", "科目明细"),
    ("审计报告", "财务", "审计报告"),
    ("财务报表", "财务", "财务报表"),
    ("财报", "财务", "财务报表"),
    ("反担保", "担保", "反担保"),
    ("担保", "担保", "担保"),
    ("征信", "征信", "征信报告"),
    ("营业执照", "工商", "营业执照"),
    ("开户许可", "工商", "开户许可证"),
    ("章程", "工商", "公司章程"),
    ("公司简介", "企业", "公司简介"),
    ("简介", "企业", "公司简介"),
    ("简历", "企业", "人员简历"),
    ("身份证", "企业", "身份证"),
]
# doc_type 标签值 → 类别
_DOCTYPE_CATEGORY = {
    "财务报表": "财务",
    "审计报告": "财务",
    "营业执照": "工商",
    "公司章程": "工商",
    "开户许可证": "工商",
    "征信报告": "征信",
    "身份证": "企业",
    "人员简历": "企业",
    "公司简介": "企业",
    "担保": "担保",
    "反担保": "担保",
}


def _doc_type_of(knowledge_id, document_id):
    """取文档的 doc_type 标签值（auto_tag_documents 已打）。无则 None。"""
    tag_ids = list(QuerySet(Tag).filter(knowledge_id=knowledge_id, key="doc_type").values_list("id", flat=True))
    if not tag_ids:
        return None
    dt = QuerySet(DocumentTag).filter(document_id=document_id, tag_id__in=tag_ids).first()
    if dt is None:
        return None
    t = QuerySet(Tag).filter(id=dt.tag_id).first()
    return t.value if t else None


def _category_doctype(doc_type, name):
    """优先用 doc_type 标签定类别，缺失则文件名兜底。返回 (类别, 文档类型)。"""
    if doc_type and doc_type in _DOCTYPE_CATEGORY:
        return _DOCTYPE_CATEGORY[doc_type], doc_type
    for kw, cat, dt in _NAME_PAIRS:
        if kw in (name or ""):
            return cat, dt
    return (doc_type or "资料"), (doc_type or "")


def build_context_tag(company, doc_type, name):
    """构造 `【公司名｜类别｜期间｜文档类型】` 前缀。"""
    years = re.findall(r"(20\d{2})", name or "")
    if years:
        period = f"{min(years)}-{max(years)}年" if len(set(years)) > 1 else f"{years[0]}年度"
    else:
        period = ""
    category, doctype = _category_doctype(doc_type, name)
    parts = [company, category]
    if period:
        parts.append(period)
    if doctype:
        parts.append(doctype)
    return "【" + "｜".join(parts) + "】"


def inject_context_titles(knowledge_id, documents: Iterable[Document]) -> int:
    """A 档：给文档段落 title 注入上下文标签前缀（幂等，先剥旧前缀）。返回改动段落数。

    调用点：batch_save 内、段落 bulk_create 之后、post_embedding 之前——这样后续
    嵌入读取的是已带标签的 title，无需重嵌入。失败吞掉不阻断上传。
    """
    if not CONTEXT_TAG_ENABLED:
        return 0
    kb = QuerySet(Knowledge).filter(id=knowledge_id).first()
    if kb is None:
        return 0
    company = kb.name
    changed = 0
    for d in documents:
        try:
            # 每文档一个 savepoint：单文档失败只回滚自身，不毒化外层 batch_save 上传事务
            # （否则一处 DB 错误会让后续所有查询抛 "can't execute queries until the end of
            # the 'atomic' block"，整批上传失败）。
            with transaction.atomic():
                doc_type = _doc_type_of(knowledge_id, d.id)
                tag = build_context_tag(company, doc_type, d.name)
                for p in QuerySet(Paragraph).filter(document_id=d.id):
                    base = re.sub(r"^【[^】]*】\s*", "", (p.title or ""))
                    new_title = (tag + (" " + base if base else "")).strip()
                    if new_title != (p.title or ""):
                        p.title = new_title
                        p.save()
                        changed += 1
        except Exception as e:  # noqa: BLE001
            maxkb_logger.warning(f"[enrich] inject title failed doc={getattr(d, 'id', None)}: {e}")
    return changed


def _fnum(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:  # noqa: BLE001
        return str(v)


def _build_summary_content(company, data):
    """data: {period: {指标: 值}} → 合并多年单段文本。"""
    lines = [f"{company} 历年主要财务指标（系统核算，单位：元）："]
    for period in sorted(data.keys()):
        d = data[period]
        at, lt = d.get("资产总计"), d.get("负债总计")
        ratio = (float(lt) / float(at) * 100) if (at and lt and float(at) != 0) else None
        seg = [f"{period}年度："]
        if at is not None:
            seg.append(f"资产总计 {_fnum(at)}")
        if lt is not None:
            seg.append(f"负债总计 {_fnum(lt)}")
        if d.get("所有者权益合计") is not None:
            seg.append(f"所有者权益合计 {_fnum(d['所有者权益合计'])}")
        if ratio is not None:
            seg.append(f"资产负债率 {ratio:.2f}%")
        if d.get("营业收入") is not None:
            seg.append(f"营业收入 {_fnum(d['营业收入'])}")
        if d.get("净利润") is not None:
            seg.append(f"净利润 {_fnum(d['净利润'])}")
        lines.append("，".join(seg) + "。")
    return "\n".join(lines)


def writeback_financial_summary(entity_names: Iterable[str]) -> int:
    """B 档：对每个 entity（公司名），从结构化财务表聚合生成"历年财务指标"摘要段落，
    upsert 到【该公司同名知识库】并嵌入。返回写出的公司数。

    entity_names 通常来自刚抽取出的 FinancialStatement.entity_name（去重）。
    仅当存在与 entity_name 同名的知识库时才写（按公司库组织）。幂等：先删旧摘要。
    失败吞掉不阻断上传。
    """
    if not FIN_SUMMARY_ENABLED:
        return 0
    done = 0
    for entity in {e for e in entity_names if e and e.strip()}:
        try:
            # 每公司一个 savepoint：单公司失败只回滚自身，不毒化外层上传事务
            with transaction.atomic():
                kb = QuerySet(Knowledge).filter(name=entity).first()
                if kb is None:
                    continue  # 无同名公司库，跳过（如噪声 entity / 聚合库本身）
                data = {}
                for s in QuerySet(FinancialStatement).filter(entity_name=entity):
                    for f in QuerySet(FinancialFact).filter(statement_id=s.id):
                        li, period = (f.line_item_normalized or ""), s.period
                        d = data.setdefault(period, {})

                        def _setk(k, _d=d, _f=f):
                            if _d.get(k) is None and _f.value is not None:
                                _d[k] = _f.value

                        if li == "资产总计":
                            _setk("资产总计")
                        elif li == "负债总计":
                            _setk("负债总计")
                        elif "所有者权益" in li and "合计" in li:
                            _setk("所有者权益合计")
                        elif li in ("主营业务收入", "营业收入"):
                            _setk("营业收入")
                        elif li == "净利润":
                            _setk("净利润")
                if not data:
                    continue
                content = _build_summary_content(entity, data)
                title = f"【{entity}｜财务｜历年财务指标摘要】"
                doc = QuerySet(Document).filter(knowledge_id=kb.id, name=SUMMARY_DOC_NAME).first()
                if doc is None:
                    doc = Document.objects.create(knowledge_id=kb.id, name=SUMMARY_DOC_NAME, char_length=0)
                else:
                    old = [str(p.id) for p in QuerySet(Paragraph).filter(document_id=doc.id)]
                    if old:
                        VectorStore.get_embedding_vector().delete_by_paragraph_ids(old)
                    QuerySet(Paragraph).filter(document_id=doc.id).delete()
                p = Paragraph(document_id=doc.id, knowledge_id=kb.id, content=content, title=title)
                p.save()
                # 单段嵌入异步入队，不阻塞上传响应
                embedding_by_paragraph.delay(str(p.id), kb.embedding_model_id)
                done += 1
        except Exception as e:  # noqa: BLE001
            maxkb_logger.warning(f"[enrich] fin summary failed entity={entity}: {e}")
    return done

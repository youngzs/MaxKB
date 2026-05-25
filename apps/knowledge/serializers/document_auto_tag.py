# coding=utf-8
"""
    @project: maxkb
    @file: document_auto_tag.py
    @desc: 上传时根据"目录路径 + 文件名"自动写 Tag / DocumentTag。

    设计：
      - Document.meta.path_segments 是 webkitdirectory / 解压后的相对路径分段；
        e.g. ['借款人资料', '盐城市保安服务有限公司', '征信报告.pdf'] 的目录段。
      - 我们把这份路径转成 3 类标签（在同一个知识库下 get-or-create）：
          path:<每一段目录名>     —— 让用户"按目录子树筛选"
          role:借款人 / 反担保人 / 担保人   —— 从首段做关键词识别
          doc_type:征信报告 / 营业执照 / ...  —— 从文件名做关键词识别
      - 规则纯 Python + 关键词表，零外部依赖。未识别的字段就不打标签，不报错。

    入参为已经 bulk_create 后的 Document 列表 —— 调用方负责保证传进来的 Document
    已经在 DB 里（拿到了 id），meta 里有 path_segments 才有意义。
"""
from typing import Iterable, List

import uuid_utils.compat as uuid
from django.db.models import QuerySet

from knowledge.models import Document, DocumentTag, Tag

# 一级目录关键词 → role 规范名。优先匹配靠前的规则（反担保必须先于担保）。
_ROLE_RULES = [
    ('反担保', '反担保人'),
    ('借款人', '借款人'),
    ('债务人', '借款人'),
    ('担保人', '担保人'),
    ('担保主体', '担保人'),
]

# 文件名关键词 → doc_type 规范名。同样按顺序匹配，第一条命中即停。
_DOC_TYPE_RULES = [
    ('营业执照', '营业执照'),
    ('征信', '征信报告'),
    ('资产负债', '财务报表'),
    ('利润表', '财务报表'),
    ('现金流', '财务报表'),
    ('财务报表', '财务报表'),
    ('财务报告', '财务报表'),
    ('审计报告', '审计报告'),
    ('章程', '公司章程'),
    ('调查报告', '调查报告'),
    ('身份证', '身份证'),
    ('授权', '授权书'),
    ('合同', '合同'),
    ('协议', '协议'),
    ('决议', '决议'),
    ('股东', '股东信息'),
    ('股权', '股权结构'),
]


def detect_role(path_segments: List[str]) -> str:
    """从相对路径首段（或前几段）猜 role。命不中返回 ''."""
    if not path_segments:
        return ''
    # 只看前两段就够了；典型形态 ['借款人资料', '盐城市保安服务有限公司', ...]
    candidates = path_segments[:2]
    haystack = ''.join(candidates)
    for kw, role in _ROLE_RULES:
        if kw in haystack:
            return role
    return ''


def detect_doc_type(name: str) -> str:
    """从文件名猜 doc_type。命不中返回 ''."""
    if not name:
        return ''
    for kw, dt in _DOC_TYPE_RULES:
        if kw in name:
            return dt
    return ''


def _get_or_create_tag(knowledge_id, key: str, value: str, cache: dict):
    """单条 get-or-create。同一次批量调用里靠 cache 避免重复 query。"""
    cache_key = (key, value)
    if cache_key in cache:
        return cache[cache_key]
    tag = QuerySet(Tag).filter(knowledge_id=knowledge_id, key=key, value=value).first()
    if tag is None:
        tag = Tag(id=uuid.uuid7(), knowledge_id=knowledge_id, key=key, value=value)
        tag.save()
    cache[cache_key] = tag
    return tag


def auto_tag_documents(knowledge_id, documents: Iterable[Document]) -> int:
    """根据 documents[i].meta.path_segments + name 自动写 Tag / DocumentTag。

    返回新建的 DocumentTag 数量。失败时记日志后继续，不抛异常 —— 自动打标不能
    阻挡正常上传流程。"""
    tag_cache: dict = {}
    new_links: list[DocumentTag] = []

    for doc in documents:
        if not doc or not doc.id:
            continue
        meta = doc.meta or {}
        segments = meta.get('path_segments') or []
        if not isinstance(segments, list):
            continue

        tags_to_link = []

        # 1) path:每一段目录名（不含最后的文件名）
        # webkitdirectory 的 path_segments 通常包含文件名作为末段，所以剥掉最后一段。
        dir_segments = segments[:-1] if len(segments) > 1 else segments
        for seg in dir_segments:
            seg = (seg or '').strip()
            if not seg:
                continue
            tags_to_link.append(('path', seg))

        # 2) role:从首/次段关键词识别
        role = detect_role(dir_segments)
        if role:
            tags_to_link.append(('role', role))

        # 3) doc_type:从文件名关键词识别
        doc_type = detect_doc_type(doc.name)
        if doc_type:
            tags_to_link.append(('doc_type', doc_type))

        if not tags_to_link:
            continue

        # 已有的 doc-tag 链接，跳过
        existing_tag_ids = set(
            str(tid) for tid in QuerySet(DocumentTag).filter(
                document_id=doc.id
            ).values_list('tag_id', flat=True)
        )

        for key, value in tags_to_link:
            try:
                tag = _get_or_create_tag(knowledge_id, key, value, tag_cache)
            except Exception:
                # tag 唯一约束冲突等极端情况——跳过，不阻挡其他标签
                continue
            if str(tag.id) in existing_tag_ids:
                continue
            new_links.append(DocumentTag(
                id=uuid.uuid7(), document_id=doc.id, tag_id=tag.id
            ))
            existing_tag_ids.add(str(tag.id))

    if new_links:
        QuerySet(DocumentTag).bulk_create(new_links, ignore_conflicts=True)

    return len(new_links)

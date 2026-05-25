# coding=utf-8
"""
    @project: maxkb
    @file: financial_extractor.py
    @desc: 从 Markdown 表格 / 段落文本里识别"资产负债表 / 利润表 / 现金流量表"，
           落到 FinancialStatement + FinancialFact 表。

    设计原则：
      - 纯规则 + 别名表，零 LLM 调用；可重复、可解释、便于人工纠正。
      - 抽取失败比抽错好 —— 任何疑难（多列重叠表头、单位混排、年份缺失）都返回
        None / 空，由调用方决定是否人工介入。
      - 入参是 markdown 表格字符串（来自 PdfSplitHandle 表格感知分块 / TextIn xparse）。
        非财务表格喂进来时 `parse_table()` 返回 None。

    用法示例：
        from knowledge.services.financial_extractor import parse_table, persist
        parsed = parse_table(md_table, default_entity='盐城市保安服务有限公司')
        if parsed:
            persist(document, parsed, raw_table_md=md_table)
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import List, Optional

# ------------------------- 别名 / 关键词表 -------------------------

# statement_type 识别：行首关键词 → 报表类型。第一条命中即定型。
_STATEMENT_TYPE_KEYWORDS = [
    # 资产负债表特征行
    ('资产合计', 'balance_sheet'),
    ('负 债 合 计', 'balance_sheet'),
    ('负债合计', 'balance_sheet'),
    ('所有者权益', 'balance_sheet'),
    ('流动资产合计', 'balance_sheet'),
    ('流动负债合计', 'balance_sheet'),
    # 利润表特征行
    ('主营业务收入', 'income_statement'),
    ('营业收入', 'income_statement'),
    ('营业利润', 'income_statement'),
    ('利润总额', 'income_statement'),
    ('净利润', 'income_statement'),
    # 现金流量表特征行
    ('经营活动产生的现金流量净额', 'cash_flow'),
    ('投资活动产生的现金流量净额', 'cash_flow'),
    ('筹资活动产生的现金流量净额', 'cash_flow'),
]

# 科目名归一化别名表。key=各种写法；value=标准名。
# 没有命中的科目保留原文（line_item_normalized = line_item）。
_LINE_ITEM_ALIASES = {
    # 资产
    '货币资金': '货币资金',
    '现金及现金等价物': '货币资金',
    '应收账款': '应收账款',
    '应收帐款': '应收账款',
    '预付账款': '预付账款',
    '预付帐款': '预付账款',
    '预付款项': '预付账款',
    '其他应收款': '其他应收款',
    '存货': '存货',
    '流动资产合计': '流动资产合计',
    '长期股权投资': '长期股权投资',
    '固定资产': '固定资产',
    '固定资产合计': '固定资产合计',
    '固定资产净值': '固定资产净值',
    '资产合计': '资产总计',
    '资产 合计': '资产总计',
    '资产总计': '资产总计',
    # 负债 & 所有者权益
    '短期借款': '短期借款',
    '应付账款': '应付账款',
    '应付帐款': '应付账款',
    '预收账款': '预收账款',
    '应付利润': '应付利润',
    '其他应付款': '其他应付款',
    '应交税金': '应交税金',
    '应交税费': '应交税金',
    '流动负债合计': '流动负债合计',
    '长期借款': '长期借款',
    '长期负债合计': '长期负债合计',
    '负债合计': '负债合计',
    '负 债 合 计': '负债合计',
    '实收资本': '实收资本',
    '资本公积': '资本公积',
    '盈余公积': '盈余公积',
    '未分配利润': '未分配利润',
    '所有者权益(或股东权益)合计': '所有者权益合计',
    '所有者权益合计': '所有者权益合计',
    '负债和所有者权益(或股东权益)总计': '负债和所有者权益总计',
    '负债和所有者权益总计': '负债和所有者权益总计',
    # 利润表
    '主营业务收入': '主营业务收入',
    '营业收入': '主营业务收入',  # 新会计准则名
    '主营业务成本': '主营业务成本',
    '营业成本': '主营业务成本',
    '主营业务税金及附加': '营业税金及附加',
    '营业税金及附加': '营业税金及附加',
    '税金及附加': '营业税金及附加',
    '主营业务利润': '主营业务利润',
    '其他业务利润': '其他业务利润',
    '管理费用': '管理费用',
    '财务费用': '财务费用',
    '销售费用': '销售费用',
    '营业费用': '销售费用',
    '营业利润': '营业利润',
    '营业外收入': '营业外收入',
    '营业外支出': '营业外支出',
    '利润总额': '利润总额',
    '所得税': '所得税费用',
    '所得税费用': '所得税费用',
    '净利润': '净利润',
}

# 单位识别：表头 / 备注里出现这些 token → 折算系数（统一到"元"）。
_UNIT_FACTORS = {
    '元': Decimal(1),
    '万元': Decimal('10000'),
    '万': Decimal('10000'),
    '千元': Decimal('1000'),
    '百万元': Decimal('1000000'),
    '亿元': Decimal('100000000'),
}

# 年度识别：4 位年份；季度 'YYYYQN'；月度 'YYYY-MM'
_YEAR_RE = re.compile(r'(20\d{2}|19\d{2})\s*年?')
_QUARTER_RE = re.compile(r'(20\d{2})\s*年?\s*[Qq]?\s*([1-4])\s*季度?')
_MONTH_RE = re.compile(r'(20\d{2})\s*[-./年]\s*(0?[1-9]|1[0-2])\s*月?')

# 数字 token：1,234,567.89 / (1,234) / -1234 / – / 空
_NUMBER_RE = re.compile(r'^[\s　]*'
                        r'(?P<sign>[-(（])?'
                        r'\s*(?P<digits>[\d,，]+(?:\.\d+)?)\s*'
                        r'[)）]?\s*$')


# ------------------------- 数据结构 -------------------------

@dataclass
class ParsedFact:
    line_item: str                 # 原文行首
    line_item_normalized: str      # 别名表归一化后
    period: str                    # 期间字符串
    value: Optional[Decimal]       # 已按 unit 单位归一（仍是表头声明的单位）
    parent_line_item: str = ''
    indent_level: int = 0


@dataclass
class ParsedStatement:
    statement_type: str            # balance_sheet / income_statement / cash_flow
    entity_name: str
    unit: str                      # '元' / '万元' / ...
    periods: List[str] = field(default_factory=list)
    period_type: str = 'annual'    # annual / quarter / month
    facts: List[ParsedFact] = field(default_factory=list)


# ------------------------- 工具函数 -------------------------

def _detect_unit(headers_blob: str) -> str:
    """从表头 / 标题里找单位声明。命中"万元"返回'万元'，未声明默认'元'。"""
    for token in ('百万元', '亿元', '万元', '千元', '万', '元'):
        if token in headers_blob:
            return token
    return '元'


def _detect_periods(header_cells: List[str]) -> tuple[List[str], str]:
    """从表头行识别期间列。返回 (periods, period_type)。
    优先尝试月度 / 季度，最后退到年度。同一表里期间类型必须一致。
    """
    months, quarters, years = [], [], []
    for cell in header_cells:
        cell = (cell or '').strip()
        if not cell:
            continue
        m_match = _MONTH_RE.search(cell)
        if m_match:
            months.append(f"{m_match.group(1)}-{int(m_match.group(2)):02d}")
            continue
        q_match = _QUARTER_RE.search(cell)
        if q_match:
            quarters.append(f"{q_match.group(1)}Q{q_match.group(2)}")
            continue
        y_match = _YEAR_RE.search(cell)
        if y_match:
            years.append(y_match.group(1))
    if months:
        return months, 'month'
    if quarters:
        return quarters, 'quarter'
    if years:
        return years, 'annual'
    return [], 'annual'


def _detect_statement_type(rows_text: str) -> Optional[str]:
    """根据出现的特征行猜报表类型。"""
    for kw, st in _STATEMENT_TYPE_KEYWORDS:
        if kw in rows_text:
            return st
    return None


def _normalize_line_item(raw: str) -> tuple[str, int]:
    """去掉缩进 / 序号 / '其中：' / 全角空格，返回 (清洁科目名, 缩进层级估计)。"""
    s = raw
    # 缩进层级：开头空格数 / 4 取整（也兼容全角空格）
    leading = len(s) - len(s.lstrip(' 　'))
    indent_level = leading // 2  # 2 个空格 = 1 级，经验值
    s = s.lstrip(' 　\t')
    # 去掉行首 "其中：" / "加:" / "减:" 这类会计前缀
    s = re.sub(r'^(其中[：:]|加\s*[:：]|减\s*[:：])\s*', '', s)
    # 去掉行首数字序号 "1." / "(1)" / "（一）"
    s = re.sub(r'^[\(（]?[一二三四五六七八九十\d]+[\)）.、]?\s*', '', s)
    # 去掉行末备注 (亏损以"-"号填列)
    s = re.sub(r'[(（].*?填列.*?[)）]\s*$', '', s).strip()
    return s, indent_level


def _normalize_to_alias(clean: str) -> str:
    """对照别名表。命中返回标准名，否则返回原文。"""
    if clean in _LINE_ITEM_ALIASES:
        return _LINE_ITEM_ALIASES[clean]
    # 去空格再试一次（资产负债表里常有 '负 债 合 计' 这种）
    nosp = re.sub(r'\s+', '', clean)
    return _LINE_ITEM_ALIASES.get(nosp, clean)


def _parse_number(token: str) -> Optional[Decimal]:
    """把单元格里的数字 token 解析成 Decimal。空 / '-' / '/' 返回 None。"""
    if token is None:
        return None
    t = token.strip().replace('　', '')
    if not t or t in ('-', '—', '/', 'N/A', 'n/a', '无'):
        return None
    m = _NUMBER_RE.match(t)
    if not m:
        return None
    sign = m.group('sign')
    digits = m.group('digits').replace(',', '').replace('，', '')
    try:
        value = Decimal(digits)
    except InvalidOperation:
        return None
    if sign in ('-', '(', '（'):
        value = -value
    return value


# ------------------------- 主解析逻辑 -------------------------

def parse_table(md_table: str, default_entity: str = '',
                explicit_periods: Optional[List[str]] = None) -> Optional[ParsedStatement]:
    """识别一个 markdown 表格是否为财务报表，是的话返回 ParsedStatement。

    md_table 必须是规范的 GitHub markdown 表格（| --- | 分隔行）。
    explicit_periods 用于"表头里没年份但调用方知道是 2024 年"的兜底。
    """
    if not md_table or '|' not in md_table:
        return None
    lines = [ln for ln in md_table.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None

    # 解析每行的单元格
    table_rows = []
    for line in lines:
        s = line.strip()
        if s.startswith('|'):
            s = s[1:]
        if s.endswith('|'):
            s = s[:-1]
        # 跳过分隔行 |---|---|
        if re.match(r'^\s*[:\-\s|]+$', s):
            continue
        cells = [c.strip() for c in s.split('|')]
        table_rows.append(cells)

    if len(table_rows) < 2:
        return None

    # 表头一般在前 1-2 行；找到第一行带年份的当表头
    header_cells = []
    body_start = 0
    for i, row in enumerate(table_rows[:3]):
        periods, _ = _detect_periods(row)
        if periods:
            header_cells = row
            body_start = i + 1
            break
    if not header_cells:
        header_cells = table_rows[0]
        body_start = 1

    periods, period_type = _detect_periods(header_cells)
    if not periods and explicit_periods:
        periods = explicit_periods
    if not periods:
        return None  # 没期间识别不出来，不是标准财务报表

    # 单位：从所有行的文本里找
    full_text = '\n'.join('|'.join(r) for r in table_rows)
    unit = _detect_unit(full_text)

    # 报表类型
    statement_type = _detect_statement_type(full_text)
    if not statement_type:
        return None

    # 期间列在表头里的位置（按 cell index 对齐）。
    # 第 0 列一般是科目；后续列对应 periods 顺序。如果列数不对，跳过这张表。
    body = table_rows[body_start:]
    # 容错：如果表头列数 ≠ 期间数 + 1，按位置取最右 N 列（典型形态）
    expected_cols = len(periods) + 1
    if not body:
        return None

    facts: List[ParsedFact] = []
    parent_stack: List[str] = []  # 记录"合计"行作为后续 child 的 parent

    for row in body:
        if len(row) < 2:
            continue
        # 第一列科目，后 N 列对齐期间
        raw_item = row[0]
        clean, indent = _normalize_line_item(raw_item)
        if not clean:
            continue
        normalized = _normalize_to_alias(clean)

        # 取数值列：若总列数恰好 = 1+期间数，按位置取；否则取最后 len(periods) 列
        if len(row) == expected_cols:
            value_cells = row[1:]
        elif len(row) > expected_cols:
            value_cells = row[-len(periods):]
        else:
            # 列数不够 —— 这一行可能是合并 / 描述行，跳过
            continue

        # parent 关系：碰到带"合计"的行后，push 进 parent_stack；再深一级的明细行
        # 把最近一个合计行作为 parent。
        # 简化版：只看 indent_level 比当前低的最近合计行。
        parent = ''
        if indent > 0 and parent_stack:
            parent = parent_stack[-1]

        for i, period in enumerate(periods):
            if i >= len(value_cells):
                value = None
            else:
                value = _parse_number(value_cells[i])
            facts.append(ParsedFact(
                line_item=clean,
                line_item_normalized=normalized,
                period=period,
                value=value,
                parent_line_item=parent,
                indent_level=indent,
            ))

        if '合计' in clean or '总计' in clean:
            parent_stack.append(clean)

    if not facts:
        return None

    return ParsedStatement(
        statement_type=statement_type,
        entity_name=default_entity,
        unit=unit,
        periods=periods,
        period_type=period_type,
        facts=facts,
    )


def persist(document, parsed: ParsedStatement, raw_table_md: str = ''):
    """把 ParsedStatement + 内部的 facts 落库。

    返回 (statement_obj, fact_count)。
    同一 document + statement_type + period 已有数据时，先删旧再插新（按主键集合
    删除避免唯一约束冲突）。
    """
    # 延迟 import 避免模块 import 早期触发 model 链路
    from django.db.models import QuerySet

    from knowledge.models import FinancialFact, FinancialStatement

    # 一份 ParsedStatement 可能跨多个 period —— 按 period 拆成多个 statement，
    # 这样问答时按 (entity, period) 取数最自然。
    fact_count = 0
    statements_created = []
    for period in parsed.periods:
        # 同 doc / type / period 已存在 → 先删
        existing = QuerySet(FinancialStatement).filter(
            document=document,
            statement_type=parsed.statement_type,
            period=period,
        )
        if existing.exists():
            QuerySet(FinancialFact).filter(statement__in=existing).delete()
            existing.delete()

        stmt = FinancialStatement.objects.create(
            document=document,
            statement_type=parsed.statement_type,
            period=period,
            period_type=parsed.period_type,
            entity_name=parsed.entity_name or '',
            unit=parsed.unit or '元',
            raw_table_md=raw_table_md or '',
        )
        statements_created.append(stmt)

        period_facts = [f for f in parsed.facts if f.period == period]
        fact_objs = [
            FinancialFact(
                statement=stmt,
                line_item=f.line_item,
                line_item_normalized=f.line_item_normalized,
                value=f.value,
                parent_line_item=f.parent_line_item,
                indent_level=f.indent_level,
            )
            for f in period_facts
        ]
        if fact_objs:
            FinancialFact.objects.bulk_create(fact_objs)
            fact_count += len(fact_objs)

    return statements_created, fact_count

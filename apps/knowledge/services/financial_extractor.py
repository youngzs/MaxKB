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

# 中国会计准则报表常用"期末/期初/本期/上期"等抽象期间标记(不带年份)。
# 命中时把列名本身作为 period 字符串入库 —— 用户后续可以通过 statement 关联
# 文档元数据/上下文还原成具体年份(Phase 4 改进项)。
# 顺序敏感:"期末余额"必须在"期末"前匹配,否则只截一半。
_RELATIVE_PERIOD_TOKENS = (
    '期末余额', '期初余额', '本期金额', '上期金额',
    '本年金额', '上年金额', '本年累计', '上年累计',
    '本期发生额', '上期发生额', '本期数', '上期数',
    '期末数', '期初数', '年初余额', '年末余额',
)

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

    优先尝试: 月度 → 季度 → 年度 → 相对期间(期末/期初/本期/上期)。
    "相对期间"是中国会计准则报表的常见表头("期末余额"/"上期金额"等);
    没有具体年份,但仍是合法的期间标识。命中时 period_type = 'relative'。
    """
    months, quarters, years, relatives = [], [], [], []
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
            continue
        # 相对期间识别:整个 cell 是单个相对期间标记 (e.g. "期末余额")
        # 不允许"局部匹配",避免误把正文段落识别成期间。
        for tok in _RELATIVE_PERIOD_TOKENS:
            if tok in cell and len(cell) <= len(tok) + 4:  # 留点容错给前缀
                relatives.append(tok)
                break
    if months:
        return months, 'month'
    if quarters:
        return quarters, 'quarter'
    if years:
        return years, 'annual'
    if relatives:
        return relatives, 'relative'
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


# ===================================================================
# 模板感知解析（国产财务软件导出的资产负债表/利润表/现金流量表）
# -------------------------------------------------------------------
# 这类报表特征：一张超宽表把"资产 | 负债和所有者权益 | 财务指标"三栏并排，
# 表头标题被铺满所有单元格（"资产负债表 | 资产负债表 | ... | col9..col15"），
# 且常被 OCR/分块拆到多个段落里。语义列由含"序号"的表头行决定，年度由
# "YYYY年度 / YYYY-12-31 / 文件名"推断。期末列=报告年度，年初/期初列=上一年度。
# ===================================================================

# 衍生财务指标别名（比率类，不在资产/负债科目别名表里）
_INDICATOR_ALIASES = {
    '资产负债率': '资产负债率', '产权比例': '产权比例',
    '流动比例': '流动比率', '流动比率': '流动比率',
    '速动比例': '速动比率', '速动比率': '速动比率',
    '营业利润率': '营业利润率', '净资产收益率': '净资产收益率',
    '总资产利润率': '总资产利润率', '总资产报酬率': '总资产利润率',
    '总资产增长率': '总资产增长率', '应收账款周转率': '应收账款周转率',
    '存货周转率': '存货周转率', '毛利率': '毛利率',
}

# 退化标题行：所有非空单元格都是"资 产 负 债 表"/"利 润 表"/"现金流量表"或"colN"
_TITLE_NOISE_RE = re.compile(
    r'^[\s　]*(资\s*产\s*负\s*债\s*表|利\s*润\s*表|现\s*金\s*流\s*量\s*表)[\s　]*$')
_COLN_RE = re.compile(r'^col\d+$')
# 表尾签名行
_FOOTER_TOKENS = ('单位负责人', '财务负责人', '制表人', '复核', '审核')


def _md_rows_from_contents(contents: List[str]) -> List[List[str]]:
    """把文档若干段落里的所有 markdown 表格行抽出，去分隔行/退化标题行。"""
    rows: List[List[str]] = []
    for content in contents:
        for line in (content or '').splitlines():
            s = line.strip()
            if not s.startswith('|'):
                continue
            s = s.strip('|')
            if re.match(r'^[\s:\-|]+$', s):  # |---|---| 分隔行
                continue
            cells = [c.strip() for c in s.split('|')]
            nonempty = [c for c in cells if c]
            if nonempty and all(_TITLE_NOISE_RE.match(c) or _COLN_RE.match(c) for c in nonempty):
                continue  # 退化标题行
            rows.append(cells)
    return rows


def _infer_reporting_year(rows: List[List[str]], filename: str = '') -> Optional[int]:
    """报告年度推断：YYYY年度 > YYYY-12-31 / YYYY年12月31日 > 文件名里的 YYYY。"""
    blob = '\n'.join('|'.join(r) for r in rows)
    m = re.search(r'(20\d{2})\s*年度', blob)
    if m:
        return int(m.group(1))
    m = re.search(r'(20\d{2})\s*[-./年]\s*12\s*[-./月]\s*31', blob)
    if m:
        return int(m.group(1))
    m = re.search(r'(20\d{2})', filename or '')
    if m:
        return int(m.group(1))
    return None


def _infer_entity(rows: List[List[str]], default: str = '') -> str:
    """主体名：'编制单位：XXX' > '单位名称' 邻格 > default。"""
    for r in rows:
        for c in r:
            m = re.search(r'编制单位[:：]\s*(\S.+?)\s*$', c or '')
            if m:
                return m.group(1).strip()
    for r in rows:
        for i, c in enumerate(r):
            if (c or '').strip() == '单位名称' and i + 1 < len(r) and r[i + 1].strip():
                return r[i + 1].strip()
    return default


def _is_footer(item: str) -> bool:
    return any(tok in item for tok in _FOOTER_TOKENS)


def _detect_doc_statement_type(contents: List[str], doc_name: str = '') -> Optional[str]:
    blob = (doc_name or '') + '\n' + '\n'.join(contents)
    if '资产负债表' in blob or '负债和所有者权益' in blob:
        return 'balance_sheet'
    if '利润表' in blob or '营业收入' in blob or '净利润' in blob:
        return 'income_statement'
    if '现金流量表' in blob or '经营活动产生的现金流量' in blob:
        return 'cash_flow'
    return None


def _add_fact(facts, seen, item_clean, normalized, period, value):
    """加入一条 fact，按 (normalized, period) 去重（保留首个非空）。"""
    if value is None:
        return
    key = (normalized, period)
    if key in seen:
        return
    seen[key] = True
    facts.append(ParsedFact(line_item=item_clean, line_item_normalized=normalized,
                            period=period, value=value))


def _parse_balance_sheet_template(rows, year, unit) -> List[ParsedFact]:
    """双栏(资产/负债)+财务指标 的资产负债表。返回 facts(period=year 末 / year-1 初)。"""
    hdr_idx = None
    for i, r in enumerate(rows):
        if '序号' in r and ('期末余额' in r or '年初余额' in r):
            hdr_idx = i
            break
    if hdr_idx is None:
        return []
    hdr = rows[hdr_idx]
    seq_idx = [j for j, c in enumerate(hdr) if c == '序号']
    regions = []  # (item_col, end_col, begin_col)
    for s in seq_idx:
        regions.append((s - 1, s + 1, s + 2))
    ind_region = None
    if '财务指标' in hdr:
        fi = hdr.index('财务指标')
        ind_region = (fi, fi + 1, fi + 2)
    end_p, begin_p = str(year), str(year - 1)
    facts: List[ParsedFact] = []
    seen = {}
    seen_ind = {}
    for r in rows[hdr_idx + 1:]:
        for (ci, ce, cb) in regions:
            if ci < 0 or ci >= len(r):
                continue
            raw = r[ci]
            if not raw or _is_footer(raw):
                continue
            clean, _ind = _normalize_line_item(raw)
            if not clean or _is_footer(clean) or clean in ('资产', '负债和所有者权益'):
                continue
            normalized = _normalize_to_alias(clean)
            _add_fact(facts, seen, clean, normalized, end_p,
                      _parse_number(r[ce]) if ce < len(r) else None)
            _add_fact(facts, seen, clean, normalized, begin_p,
                      _parse_number(r[cb]) if cb < len(r) else None)
        if ind_region:
            ii, ie, ib = ind_region
            if ii < len(r):
                iname = (r[ii] or '').strip()
                if iname in _INDICATOR_ALIASES:
                    inorm = _INDICATOR_ALIASES[iname]
                    _add_fact(facts, seen_ind, iname, inorm, end_p,
                              _parse_number(r[ie]) if ie < len(r) else None)
                    _add_fact(facts, seen_ind, iname, inorm, begin_p,
                              _parse_number(r[ib]) if ib < len(r) else None)
    return facts


def _parse_single_column_template(rows, year, statement_type) -> List[ParsedFact]:
    """利润表/现金流量表：科目 + 序号 + 本年累计金额/本期金额(年度值)。"""
    value_keys = ('本年累计金额', '本期金额', '本年金额', '本期发生额', '本年数', '金额')
    hdr_idx, val_col = None, None
    for i, r in enumerate(rows):
        if '序号' in r:
            for k in value_keys:
                if k in r:
                    hdr_idx, val_col = i, r.index(k)
                    break
        if hdr_idx is not None:
            break
    if hdr_idx is None:
        return []
    hdr = rows[hdr_idx]
    item_col = hdr.index('序号') - 1
    if item_col < 0:
        item_col = 0
    facts: List[ParsedFact] = []
    seen = {}
    for r in rows[hdr_idx + 1:]:
        if item_col >= len(r):
            continue
        raw = r[item_col]
        if not raw or _is_footer(raw):
            continue
        clean, _ind = _normalize_line_item(raw)
        if not clean or _is_footer(clean):
            continue
        normalized = _normalize_to_alias(clean)
        _add_fact(facts, seen, clean, normalized, str(year),
                  _parse_number(r[val_col]) if val_col < len(r) else None)
    return facts


def parse_document(contents: List[str], doc_name: str = '', filename: str = '',
                   default_entity: str = '') -> Optional[ParsedStatement]:
    """文档级模板感知解析。把一篇报表文档(可能跨多段落/多分块)整体解析成
    一个 ParsedStatement(期末=报告年度, 年初=上一年度; 含衍生财务指标)。
    识别不出标准模板时返回 None，由调用方回退到旧的 parse_table。"""
    rows = _md_rows_from_contents(contents)
    if len(rows) < 2:
        return None
    statement_type = _detect_doc_statement_type(contents, doc_name)
    if not statement_type:
        return None
    year = _infer_reporting_year(rows, filename)
    if year is None:
        return None
    full_text = '\n'.join('|'.join(r) for r in rows)
    unit = _detect_unit(full_text)
    entity = _infer_entity(rows, default_entity)

    if statement_type == 'balance_sheet':
        facts = _parse_balance_sheet_template(rows, year, unit)
        periods = [str(year), str(year - 1)]
    else:
        facts = _parse_single_column_template(rows, year, statement_type)
        periods = [str(year)]
    if not facts:
        return None
    periods = [p for p in periods if any(f.period == p for f in facts)]
    return ParsedStatement(
        statement_type=statement_type,
        entity_name=entity or '',
        unit=unit,
        periods=periods,
        period_type='annual',
        facts=facts,
    )


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

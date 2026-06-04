# coding=utf-8
"""
    @project: MaxKB
    @file: base_financial_calc_node.py
    @desc: financial-calc-node 的默认实现。

    所有函数的输出 JSON 形状：
      { "found": bool, "result": <number|list|dict>, "sources": [doc_id, ...], "message": str }
    上层 ai_chat_step_node / RAG 调用方可以直接把 result 引入答案、用 sources 引用文档。
"""
import re
from decimal import Decimal
from typing import Optional

from django.db.models import QuerySet

from application.flow.i_step_node import NodeResult
from application.flow.step_node.financial_calc_node.i_financial_calc_node import IFinancialCalcNode
from knowledge.models import FinancialFact
from knowledge.services.financial_extractor import _normalize_to_alias


def _annual_periods(entity, statement_type):
    """返回该 entity 某报表类型下、形如 4 位年份的期间（过滤掉 '2022-01'/'本期金额' 等噪声）。"""
    from knowledge.models import FinancialStatement
    ps = set(FinancialStatement.objects.filter(
        entity_name=entity, statement_type=statement_type).values_list('period', flat=True))
    return sorted(p for p in ps if re.match(r'^\d{4}$', str(p or '')))


def _fact_yuan(entity, period, line_item, statement_type, alts=None):
    """取一条 fact 折算到元；line_item 不命中时按 alts 依次回退。返回 (Decimal|None, fact|None)。"""
    f = _find_fact(entity, period, line_item, statement_type)
    if f is None and alts:
        for a in alts:
            f = _find_fact(entity, period, a, statement_type)
            if f is not None:
                break
    if f is None:
        return None, None
    return _to_yuan(f), f


def _md_table(periods, metric_rows):
    """metric_rows = [(label, [cell, ...]), ...]；生成 Markdown 表（首列=指标）。"""
    header = '| 指标 | ' + ' | '.join(periods) + ' |'
    sep = '| --- | ' + ' | '.join(['---'] * len(periods)) + ' |'
    lines = [header, sep]
    for label, cells in metric_rows:
        lines.append('| ' + label + ' | ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def _facts_query(entity: str, period: str = '', statement_type: str = ''):
    """统一构造 FinancialFact 查询。entity 是 statement 上的字段，所以走 statement__ 反查。"""
    q = QuerySet(FinancialFact)
    if entity:
        q = q.filter(statement__entity_name=entity)
    if period:
        q = q.filter(statement__period=period)
    if statement_type:
        q = q.filter(statement__statement_type=statement_type)
    return q


def _to_yuan(fact: FinancialFact) -> Optional[Decimal]:
    """把 fact.value 折算到"元"。单位在 statement 上。"""
    if fact.value is None:
        return None
    unit = (fact.statement.unit or '元').strip()
    factors = {'元': Decimal(1), '万元': Decimal('10000'), '万': Decimal('10000'),
               '千元': Decimal('1000'), '百万元': Decimal('1000000'),
               '亿元': Decimal('100000000')}
    return fact.value * factors.get(unit, Decimal(1))


def _format_amount(amount: Optional[Decimal], unit: str = '元') -> str:
    """格式化金额给人类读：金额够大时自动换万元 / 亿元单位。仅供文本输出，不影响计算。"""
    if amount is None:
        return 'N/A'
    abs_amt = abs(amount)
    if abs_amt >= Decimal('100000000'):
        return f"{amount / Decimal('100000000'):,.2f} 亿{unit}"
    if abs_amt >= Decimal('10000'):
        return f"{amount / Decimal('10000'):,.2f} 万{unit}"
    return f"{amount:,.2f} {unit}"


def _find_fact(entity: str, period: str, line_item: str,
               statement_type: str = '') -> Optional[FinancialFact]:
    """精确查一条 fact。line_item 先按归一化别名查；不命中再按原文 fuzzy。"""
    normalized = _normalize_to_alias(line_item)
    q = _facts_query(entity, period, statement_type).filter(
        line_item_normalized=normalized
    ).select_related('statement')
    fact = q.first()
    if fact is not None:
        return fact
    # fallback: 原文包含匹配
    q2 = _facts_query(entity, period, statement_type).filter(
        line_item__icontains=line_item
    ).select_related('statement')
    return q2.first()


class BaseFinancialCalcNode(IFinancialCalcNode):
    def save_context(self, details, workflow_manage):
        self.context['function'] = details.get('function')
        self.context['result'] = details.get('result')
        self.context['found'] = details.get('found')
        self.context['sources'] = details.get('sources')
        self.context['message'] = details.get('message')
        self.context['data'] = details.get('data')  # 给 LLM 节点引用用

    @staticmethod
    def _resolve_entity(raw):
        """把 entity 解析成库里真实存在的 entity_name，容忍上游抽取不准。
        - 精确命中 → 原样返回
        - 否则在已知 entity_name 里找"互为子串"的一个（支持直接把整句问题传进来，
          如『丰县智禾现代农业有限公司的偿债能力分析』→ 命中『丰县智禾现代农业有限公司』）
        这样即使 parameter-extraction 节点返回的 key 不是 entity（LLM 偶发用中文label当key
        导致引用解析为空）或带噪声，也能稳。
        """
        from knowledge.models import FinancialStatement
        raw = (raw or '').strip()
        if not raw:
            return raw
        if FinancialStatement.objects.filter(entity_name=raw).exists():
            return raw
        names = [n for n in set(
            FinancialStatement.objects.values_list('entity_name', flat=True)) if n]
        # 优先最长匹配，避免短名误命中
        for n in sorted(names, key=len, reverse=True):
            if n in raw or raw in n:
                return n
        return raw

    def execute(self, function, entity='', period='', periods=None, line_item='',
                line_items=None, numerator='', denominator='', statement_type='',
                **kwargs) -> NodeResult:
        periods = periods or []
        line_items = line_items or []
        entity = self._resolve_entity(entity)

        if function == 'get_fact':
            payload = self._fn_get_fact(entity, period, line_item, statement_type)
        elif function == 'compare_periods':
            payload = self._fn_compare_periods(entity, periods, line_item, statement_type)
        elif function == 'ratio':
            payload = self._fn_ratio(entity, period, numerator, denominator)
        elif function == 'sum_items':
            payload = self._fn_sum_items(entity, period, line_items, statement_type)
        elif function == 'list_facts':
            payload = self._fn_list_facts(entity, period, statement_type)
        elif function == 'solvency_table':
            payload = self._fn_solvency_table(entity, periods)
        elif function == 'profitability_table':
            payload = self._fn_profitability_table(entity, periods)
        elif function == 'operation_table':
            payload = self._fn_operation_table(entity, periods)
        elif function == 'financial_profile':
            payload = self._fn_financial_profile(entity, periods)
        elif function == 'statement_table':
            payload = self._fn_statement_table(entity, statement_type, periods)
        else:
            payload = {'found': False, 'result': None, 'sources': [],
                       'message': f'未知函数：{function}'}

        # 给 LLM 节点引用的字符串版本
        payload['function'] = function
        payload['data'] = self._payload_to_text(payload)
        return NodeResult(payload, {})

    # ---------- 5 个核心函数 ----------

    @staticmethod
    def _fn_get_fact(entity, period, line_item, statement_type):
        if not entity or not period or not line_item:
            return {'found': False, 'result': None, 'sources': [],
                    'message': '参数不全：需要 entity、period、line_item'}
        fact = _find_fact(entity, period, line_item, statement_type)
        if fact is None:
            return {'found': False, 'result': None, 'sources': [],
                    'message': f'{entity} {period} 期没有"{line_item}"的结构化数据'}
        amount_yuan = _to_yuan(fact)
        return {
            'found': True,
            'result': str(amount_yuan) if amount_yuan is not None else None,
            'amount_display': _format_amount(amount_yuan),
            'line_item': fact.line_item_normalized,
            'period': fact.statement.period,
            'unit_source': fact.statement.unit,
            'sources': [str(fact.statement.document_id)],
            'message': 'ok',
        }

    @staticmethod
    def _fn_compare_periods(entity, periods, line_item, statement_type):
        if not entity or not periods or not line_item:
            return {'found': False, 'result': None, 'sources': [],
                    'message': '参数不全：需要 entity、periods、line_item'}
        rows = []
        sources = set()
        last_value: Optional[Decimal] = None
        for p in periods:
            fact = _find_fact(entity, p, line_item, statement_type)
            value = _to_yuan(fact) if fact else None
            yoy = None
            if value is not None and last_value is not None and last_value != 0:
                yoy = float((value - last_value) / abs(last_value) * 100)
            rows.append({
                'period': p,
                'value': str(value) if value is not None else None,
                'amount_display': _format_amount(value),
                'change_pct_vs_prev': round(yoy, 2) if yoy is not None else None,
            })
            if fact is not None:
                sources.add(str(fact.statement.document_id))
            last_value = value
        any_found = any(r['value'] is not None for r in rows)
        return {
            'found': any_found,
            'result': rows,
            'line_item': _normalize_to_alias(line_item),
            'sources': list(sources),
            'message': 'ok' if any_found else f'{entity} 所有期都没有"{line_item}"',
        }

    @staticmethod
    def _fn_ratio(entity, period, numerator, denominator):
        if not entity or not period or not numerator or not denominator:
            return {'found': False, 'result': None, 'sources': [],
                    'message': '参数不全：需要 entity、period、numerator、denominator'}
        f_num = _find_fact(entity, period, numerator)
        f_den = _find_fact(entity, period, denominator)
        if f_num is None or f_den is None:
            missing = [name for name, f in [(numerator, f_num), (denominator, f_den)] if f is None]
            return {'found': False, 'result': None, 'sources': [],
                    'message': f'缺少科目：{", ".join(missing)}'}
        v_num = _to_yuan(f_num)
        v_den = _to_yuan(f_den)
        if v_num is None or v_den is None or v_den == 0:
            return {'found': False, 'result': None, 'sources': [],
                    'message': '分子或分母为空 / 分母为 0'}
        ratio_val = float(v_num / v_den)
        sources = list({str(f_num.statement.document_id), str(f_den.statement.document_id)})
        return {
            'found': True,
            'result': round(ratio_val, 4),
            'ratio_pct': round(ratio_val * 100, 2),
            'numerator': {
                'line_item': f_num.line_item_normalized,
                'value': str(v_num),
                'amount_display': _format_amount(v_num),
            },
            'denominator': {
                'line_item': f_den.line_item_normalized,
                'value': str(v_den),
                'amount_display': _format_amount(v_den),
            },
            'period': period,
            'sources': sources,
            'message': 'ok',
        }

    @staticmethod
    def _fn_sum_items(entity, period, line_items, statement_type):
        if not entity or not period or not line_items:
            return {'found': False, 'result': None, 'sources': [],
                    'message': '参数不全：需要 entity、period、line_items'}
        total = Decimal(0)
        items_detail = []
        sources = set()
        missing = []
        for li in line_items:
            fact = _find_fact(entity, period, li, statement_type)
            if fact is None:
                missing.append(li)
                items_detail.append({'line_item': li, 'value': None})
                continue
            v = _to_yuan(fact)
            if v is None:
                items_detail.append({'line_item': li, 'value': None})
                continue
            total += v
            items_detail.append({
                'line_item': fact.line_item_normalized,
                'value': str(v),
                'amount_display': _format_amount(v),
            })
            sources.add(str(fact.statement.document_id))
        return {
            'found': len(missing) < len(line_items),
            'result': str(total),
            'amount_display': _format_amount(total),
            'items': items_detail,
            'missing': missing,
            'period': period,
            'sources': list(sources),
            'message': 'ok' if not missing else f'有 {len(missing)} 个科目缺数：{missing}',
        }

    @staticmethod
    def _fn_list_facts(entity, period, statement_type):
        if not entity or not period:
            return {'found': False, 'result': None, 'sources': [],
                    'message': '参数不全：需要 entity、period'}
        facts = list(_facts_query(entity, period, statement_type).select_related('statement'))
        if not facts:
            return {'found': False, 'result': [], 'sources': [],
                    'message': f'{entity} {period} 期没有任何结构化数据'}
        items = []
        sources = set()
        for f in facts:
            v = _to_yuan(f)
            items.append({
                'line_item': f.line_item_normalized,
                'value': str(v) if v is not None else None,
                'amount_display': _format_amount(v),
                'statement_type': f.statement.statement_type,
            })
            sources.add(str(f.statement.document_id))
        return {
            'found': True,
            'result': items,
            'count': len(items),
            'period': period,
            'sources': list(sources),
            'message': 'ok',
        }

    @staticmethod
    def _num(v, fmt='{:.2f}', pct=False):
        if v is None:
            return 'N/A'
        return (fmt.format(v) + '%') if pct else fmt.format(v)

    @classmethod
    def _fn_solvency_table(cls, entity, periods=None):
        """偿债能力分析表：流动比率 / 速动比率 / 资产负债率 × 多期。
        速动比率含减法 (流动资产合计-存货)/流动负债合计；负债/资产总计带 总计/合计 别名回退。
        periods 为空自动取资产负债表全部年度。"""
        if not entity:
            return {'found': False, 'result': None, 'sources': [], 'message': '参数不全：需要 entity'}
        periods = periods or _annual_periods(entity, 'balance_sheet')
        if not periods:
            return {'found': False, 'result': None, 'sources': [], 'message': f'{entity} 没有资产负债表结构化数据'}
        rows, sources = [], set()
        for p in periods:
            ca, f1 = _fact_yuan(entity, p, '流动资产合计', 'balance_sheet')
            cl, f2 = _fact_yuan(entity, p, '流动负债合计', 'balance_sheet')
            inv, f3 = _fact_yuan(entity, p, '存货', 'balance_sheet')
            tl, f4 = _fact_yuan(entity, p, '负债总计', 'balance_sheet', ['负债合计'])
            ta, f5 = _fact_yuan(entity, p, '资产总计', 'balance_sheet', ['资产合计'])
            for f in (f1, f2, f3, f4, f5):
                if f is not None:
                    sources.add(str(f.statement.document_id))
            cur = float(ca / cl) if (ca is not None and cl not in (None, 0)) else None
            quick = float((ca - (inv or Decimal(0))) / cl) if (ca is not None and cl not in (None, 0)) else None
            debt = float(tl / ta * 100) if (tl is not None and ta not in (None, 0)) else None
            rows.append({'period': p, 'current_ratio': cur, 'quick_ratio': quick, 'debt_asset_ratio_pct': debt})
        table = _md_table(periods, [
            ('流动比率', [cls._num(r['current_ratio']) for r in rows]),
            ('速动比率', [cls._num(r['quick_ratio']) for r in rows]),
            ('资产负债率', [cls._num(r['debt_asset_ratio_pct'], pct=True) for r in rows]),
        ])
        found = any(r['current_ratio'] is not None or r['debt_asset_ratio_pct'] is not None for r in rows)
        return {'found': found, 'result': rows, 'periods': periods, 'sources': list(sources),
                'table_md': table, 'message': 'ok' if found else f'{entity} 偿债指标结构化数据不足'}

    @classmethod
    def _fn_profitability_table(cls, entity, periods=None):
        """盈利能力分析表：毛利率 / 净利率 / 净资产收益率(ROE) × 多期。
        毛利率=(主营业务收入-主营业务成本)/主营业务收入；净利率=净利润/主营业务收入；
        ROE=净利润/所有者权益合计（净利来自利润表，权益来自资产负债表）。"""
        if not entity:
            return {'found': False, 'result': None, 'sources': [], 'message': '参数不全：需要 entity'}
        periods = periods or _annual_periods(entity, 'income_statement')
        if not periods:
            return {'found': False, 'result': None, 'sources': [], 'message': f'{entity} 没有利润表年度数据'}
        rows, sources = [], set()
        for p in periods:
            rev, f1 = _fact_yuan(entity, p, '主营业务收入', 'income_statement', ['营业收入'])
            cost, f2 = _fact_yuan(entity, p, '主营业务成本', 'income_statement', ['营业成本'])
            ni, f3 = _fact_yuan(entity, p, '净利润', 'income_statement')
            eq, f4 = _fact_yuan(entity, p, '所有者权益合计', 'balance_sheet',
                                ['所有者权益（或股东权益）合计', '股东权益合计'])
            for f in (f1, f2, f3, f4):
                if f is not None:
                    sources.add(str(f.statement.document_id))
            gross = float((rev - cost) / rev * 100) if (rev not in (None, 0) and cost is not None) else None
            net = float(ni / rev * 100) if (ni is not None and rev not in (None, 0)) else None
            roe = float(ni / eq * 100) if (ni is not None and eq not in (None, 0)) else None
            rows.append({'period': p, 'gross_margin_pct': gross, 'net_margin_pct': net, 'roe_pct': roe})
        table = _md_table(periods, [
            ('毛利率', [cls._num(r['gross_margin_pct'], pct=True) for r in rows]),
            ('净利率', [cls._num(r['net_margin_pct'], pct=True) for r in rows]),
            ('净资产收益率(ROE)', [cls._num(r['roe_pct'], pct=True) for r in rows]),
        ])
        found = any(r['net_margin_pct'] is not None or r['gross_margin_pct'] is not None for r in rows)
        return {'found': found, 'result': rows, 'periods': periods, 'sources': list(sources),
                'table_md': table, 'message': 'ok' if found else f'{entity} 盈利指标结构化数据不足'}

    @classmethod
    def _fn_operation_table(cls, entity, periods=None):
        """营运能力分析表：应收账款周转率 / 存货周转率 / 总资产周转率 × 多期（期末值近似）。
        应收周转=主营业务收入/应收账款；存货周转=主营业务成本/存货；总资产周转=主营业务收入/资产总计。"""
        if not entity:
            return {'found': False, 'result': None, 'sources': [], 'message': '参数不全：需要 entity'}
        periods = periods or _annual_periods(entity, 'income_statement')
        if not periods:
            return {'found': False, 'result': None, 'sources': [], 'message': f'{entity} 没有利润表年度数据'}
        rows, sources = [], set()
        for p in periods:
            rev, f1 = _fact_yuan(entity, p, '主营业务收入', 'income_statement', ['营业收入'])
            cost, f2 = _fact_yuan(entity, p, '主营业务成本', 'income_statement', ['营业成本'])
            ar, f3 = _fact_yuan(entity, p, '应收账款', 'balance_sheet')
            inv, f4 = _fact_yuan(entity, p, '存货', 'balance_sheet')
            ta, f5 = _fact_yuan(entity, p, '资产总计', 'balance_sheet', ['资产合计'])
            for f in (f1, f2, f3, f4, f5):
                if f is not None:
                    sources.add(str(f.statement.document_id))
            ar_turn = float(rev / ar) if (rev is not None and ar not in (None, 0)) else None
            inv_turn = float(cost / inv) if (cost is not None and inv not in (None, 0)) else None
            ta_turn = float(rev / ta) if (rev is not None and ta not in (None, 0)) else None
            rows.append({'period': p, 'ar_turnover': ar_turn, 'inv_turnover': inv_turn, 'ta_turnover': ta_turn})
        table = _md_table(periods, [
            ('应收账款周转率(次)', [cls._num(r['ar_turnover']) for r in rows]),
            ('存货周转率(次)', [cls._num(r['inv_turnover']) for r in rows]),
            ('总资产周转率(次)', [cls._num(r['ta_turnover']) for r in rows]),
        ])
        found = any(r['ar_turnover'] is not None or r['ta_turnover'] is not None for r in rows)
        return {'found': found, 'result': rows, 'periods': periods, 'sources': list(sources),
                'table_md': table, 'message': 'ok' if found else f'{entity} 营运指标结构化数据不足'}

    @classmethod
    def _fn_financial_profile(cls, entity, periods=None):
        """企业财务综合画像：规模(资产总计/营收/净利润) + 偿债 + 盈利 + 营运 多表合一。"""
        if not entity:
            return {'found': False, 'result': None, 'sources': [], 'message': '参数不全：需要 entity'}
        bs_periods = _annual_periods(entity, 'balance_sheet')
        # 规模表（按资产负债表年度）
        size_rows, sources = [], set()
        for p in (bs_periods or []):
            ta, f1 = _fact_yuan(entity, p, '资产总计', 'balance_sheet', ['资产合计'])
            rev, f2 = _fact_yuan(entity, p, '主营业务收入', 'income_statement', ['营业收入'])
            ni, f3 = _fact_yuan(entity, p, '净利润', 'income_statement')
            for f in (f1, f2, f3):
                if f is not None:
                    sources.add(str(f.statement.document_id))
            size_rows.append({'period': p, 'ta': ta, 'rev': rev, 'ni': ni})
        size_md = _md_table(bs_periods or [], [
            ('资产总计', [_format_amount(r['ta']) for r in size_rows]),
            ('营业收入', [_format_amount(r['rev']) for r in size_rows]),
            ('净利润', [_format_amount(r['ni']) for r in size_rows]),
        ]) if bs_periods else '（无年度数据）'
        solv = cls._fn_solvency_table(entity)
        prof = cls._fn_profitability_table(entity)
        oper = cls._fn_operation_table(entity)
        for sub in (solv, prof, oper):
            for s in (sub.get('sources') or []):
                sources.add(s)
        combined = (
            f"### {entity} 财务综合画像\n\n"
            f"**一、规模指标**\n{size_md}\n\n"
            f"**二、偿债能力**\n{solv.get('table_md', '（数据不足）')}\n\n"
            f"**三、盈利能力**\n{prof.get('table_md', '（数据不足）')}\n\n"
            f"**四、营运能力**\n{oper.get('table_md', '（数据不足）')}"
        )
        found = bool(bs_periods) or solv.get('found') or prof.get('found')
        return {'found': found, 'result': {'size': size_rows}, 'periods': bs_periods,
                'sources': list(sources), 'table_md': combined,
                'message': 'ok' if found else f'{entity} 财务结构化数据不足'}

    @classmethod
    def _fn_statement_table(cls, entity, statement_type='balance_sheet', periods=None):
        """完整原始报表：把某报表类型(资产负债表/利润表/现金流量表)逐行科目 × 多期透视成 Markdown 表。
        periods 为空自动取该报表全部年度；保留科目首次出现顺序。"""
        from knowledge.models import FinancialFact
        if not entity:
            return {'found': False, 'result': None, 'sources': [], 'message': '参数不全：需要 entity'}
        st = statement_type or 'balance_sheet'
        periods = periods or _annual_periods(entity, st)
        if not periods:
            return {'found': False, 'result': None, 'sources': [],
                    'message': f'{entity} 没有{st}年度数据'}
        order, seen, data, sources = [], set(), {}, set()
        for p in periods:
            facts = list(FinancialFact.objects.filter(
                statement__entity_name=entity, statement__period=p,
                statement__statement_type=st).select_related('statement'))
            pm = {}
            for f in facts:
                li = f.line_item_normalized
                if li and li not in seen:
                    seen.add(li); order.append(li)
                v = _to_yuan(f)
                pm[li] = _format_amount(v)
                sources.add(str(f.statement.document_id))
            data[p] = pm
        title = {'balance_sheet': '资产负债表', 'income_statement': '利润表',
                 'cash_flow': '现金流量表'}.get(st, st)
        header = '| 科目 | ' + ' | '.join(periods) + ' |'
        sep = '| --- | ' + ' | '.join(['---'] * len(periods)) + ' |'
        body = ['| ' + li + ' | ' + ' | '.join(data[p].get(li, '') for p in periods) + ' |'
                for li in order]
        table = f"**{entity} {title}**\n" + '\n'.join([header, sep] + body)
        return {'found': bool(order), 'result': {'order': order, 'data': data}, 'periods': periods,
                'sources': list(sources), 'table_md': table,
                'message': 'ok' if order else f'{entity} {title}无数据'}

    # ---------- 文本化（供 LLM 节点引用） ----------

    @staticmethod
    def _payload_to_text(payload: dict) -> str:
        """把结构化 payload 转成自然语言摘要。LLM 节点可以把它当 reference 引用。"""
        if not payload.get('found'):
            return payload.get('message') or '未找到数据'
        fn = payload.get('function')
        if fn == 'get_fact':
            return (f"{payload.get('line_item')}（{payload.get('period')}）= "
                    f"{payload.get('amount_display')}")
        if fn == 'compare_periods':
            rows = payload.get('result') or []
            lines = [f"- {r['period']}：{r['amount_display']}"
                     + (f"（同比 {r['change_pct_vs_prev']}%）" if r['change_pct_vs_prev'] is not None else '')
                     for r in rows]
            return f"{payload.get('line_item')} 各期对比：\n" + '\n'.join(lines)
        if fn == 'ratio':
            num = payload.get('numerator', {})
            den = payload.get('denominator', {})
            return (f"{num.get('line_item')} / {den.get('line_item')}"
                    f"（{payload.get('period')}）= {payload.get('ratio_pct')}%\n"
                    f"  分子 {num.get('amount_display')}；分母 {den.get('amount_display')}")
        if fn == 'sum_items':
            items = payload.get('items') or []
            lines = [f"- {it['line_item']}：{it.get('amount_display','N/A')}" for it in items]
            return (f"求和（{payload.get('period')}）= {payload.get('amount_display')}\n"
                    + '\n'.join(lines))
        if fn == 'list_facts':
            items = payload.get('result') or []
            return (f"{payload.get('period')} 期共 {payload.get('count')} 个科目：\n"
                    + '\n'.join(f"- {it['line_item']}：{it.get('amount_display','N/A')}"
                                for it in items[:50]))
        if fn in ('solvency_table', 'profitability_table', 'operation_table',
                  'financial_profile', 'statement_table'):
            return payload.get('table_md') or ''
        return ''

    def get_details(self, index: int, **kwargs):
        return {
            'name': self.node.properties.get('stepName'),
            'function': self.context.get('function'),
            'found': self.context.get('found'),
            'result': self.context.get('result'),
            'sources': self.context.get('sources'),
            'message': self.context.get('message'),
            'data': self.context.get('data'),
            'index': index,
            'run_time': self.context.get('run_time'),
            'type': self.node.type,
            'status': self.status,
            'err_message': self.err_message,
        }

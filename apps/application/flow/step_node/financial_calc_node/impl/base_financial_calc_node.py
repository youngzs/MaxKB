# coding=utf-8
"""
    @project: MaxKB
    @file: base_financial_calc_node.py
    @desc: financial-calc-node 的默认实现。

    所有函数的输出 JSON 形状：
      { "found": bool, "result": <number|list|dict>, "sources": [doc_id, ...], "message": str }
    上层 ai_chat_step_node / RAG 调用方可以直接把 result 引入答案、用 sources 引用文档。
"""
from decimal import Decimal
from typing import Optional

from django.db.models import QuerySet

from application.flow.i_step_node import NodeResult
from application.flow.step_node.financial_calc_node.i_financial_calc_node import IFinancialCalcNode
from knowledge.models import FinancialFact
from knowledge.services.financial_extractor import _normalize_to_alias


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

    def execute(self, function, entity='', period='', periods=None, line_item='',
                line_items=None, numerator='', denominator='', statement_type='',
                **kwargs) -> NodeResult:
        periods = periods or []
        line_items = line_items or []

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

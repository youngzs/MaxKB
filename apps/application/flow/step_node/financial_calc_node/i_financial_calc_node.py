# coding=utf-8
"""
    @project: MaxKB
    @file: i_financial_calc_node.py
    @desc: 财务确定性计算节点 — 把"算"从 LLM 手上拿下来。

    设计：
      - 节点暴露 5 个函数：get_fact / compare_periods / ratio / sum_items / list_facts
      - 全部从 FinancialFact 表精确取数，再用 Python 算（不走 LLM）
      - 每个返回值都带"数据来源"（document_id / statement_id），便于回答时引用

    上层路由（intent_node）建议：
        question 命中 "算 / 对比 / 趋势 / 比率 / 同比 / 环比 / 总额" 等关键词
        → 走本节点
        → 找不到该 entity/period/line_item 时返回 { found: false }，调用方降级到 RAG
"""
import re
from typing import Type

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from application.flow.common import WorkflowMode
from application.flow.i_step_node import INode, NodeResult

# 支持的函数名（同步前端 enum）。
ALL_FUNCTIONS = (
    'get_fact',           # 单点取数
    'compare_periods',    # 多期对比 + 同比/环比
    'ratio',              # 比率：numerator / denominator
    'sum_items',          # 多科目求和
    'list_facts',         # 列出某主体某期全部已抽科目
    'solvency_table',       # 偿债能力分析表：流动比率/速动比率/资产负债率 × 多期
    'profitability_table',  # 盈利能力分析表：毛利率/净利率/ROE × 多期
    'operation_table',      # 营运能力分析表：应收/存货/总资产周转率 × 多期
    'financial_profile',    # 企业财务综合画像：规模+偿债+盈利+营运 多表合一
    'statement_table',      # 完整原始报表：资产负债表/利润表/现金流量表 逐行 × 多期
)


class FinancialCalcNodeParamsSerializer(serializers.Serializer):
    function = serializers.ChoiceField(
        choices=ALL_FUNCTIONS, required=True, label=_('Function')
    )
    # 通用参数（不同 function 用不同子集，节点内部按 function 解析）
    entity = serializers.CharField(required=False, allow_blank=True, default='',
                                   label=_('Entity name'))
    period = serializers.CharField(required=False, allow_blank=True, default='',
                                   label=_('Period'))
    periods = serializers.ListField(required=False, default=list,
                                    child=serializers.CharField(),
                                    label=_('Periods'))
    line_item = serializers.CharField(required=False, allow_blank=True, default='',
                                      label=_('Line item'))
    line_items = serializers.ListField(required=False, default=list,
                                       child=serializers.CharField(),
                                       label=_('Line items'))
    numerator = serializers.CharField(required=False, allow_blank=True, default='',
                                      label=_('Numerator'))
    denominator = serializers.CharField(required=False, allow_blank=True, default='',
                                        label=_('Denominator'))
    statement_type = serializers.CharField(required=False, allow_blank=True, default='',
                                           label=_('Statement type'))


class IFinancialCalcNode(INode):
    type = 'financial-calc-node'
    support = [
        WorkflowMode.APPLICATION, WorkflowMode.APPLICATION_LOOP,
        WorkflowMode.TOOL, WorkflowMode.TOOL_LOOP,
    ]

    def get_node_params_serializer_class(self) -> Type[serializers.Serializer]:
        return FinancialCalcNodeParamsSerializer

    def _resolve_ref(self, value):
        """把字段里的 {{节点名.字段}} 引用解析成上游节点的实际输出值。

        本节点之前从没被任何工作流接过，_run 直接吃 serializer.data，
        所以 entity/period 等字段写成 {{抽取参数.entity}} 时不会被替换。
        这里复用 workflow_manage.generate_prompt（其它 15 个节点的标准做法）
        把引用渲染掉；纯字面量（不含 {{ ）原样返回。
        """
        if isinstance(value, str) and '{{' in value:
            try:
                return (self.workflow_manage.generate_prompt(value) or '').strip()
            except Exception:
                return ''
        return value

    def _run(self):
        # valid_args 已校验过 node_params_serializer，这里在执行前把引用解析掉
        data = dict(self.node_params_serializer.data)
        resolved = {}
        for key, value in data.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_ref(value)
            elif isinstance(value, list):
                # 列表字段（periods / line_items）：逐项解析；引用解析后允许用
                # 逗号/顿号/换行/分号再拆成多项（方便上游用单个字符串带多期）
                items = []
                for item in value:
                    if isinstance(item, str) and '{{' in item:
                        rv = self._resolve_ref(item)
                        items.extend([s.strip() for s in re.split(r'[,\n、，;；]', rv) if s.strip()])
                    elif isinstance(item, str):
                        if item.strip():
                            items.append(item.strip())
                    else:
                        items.append(item)
                resolved[key] = items
            else:
                resolved[key] = value
        return self.execute(**resolved)

    def execute(self, function, **kwargs) -> NodeResult:
        pass

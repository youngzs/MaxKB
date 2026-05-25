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

    def _run(self):
        return self.execute(**self.node_params_serializer.data)

    def execute(self, function, **kwargs) -> NodeResult:
        pass

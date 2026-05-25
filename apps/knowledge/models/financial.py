# coding=utf-8
"""
    @project: maxkb
    @file: financial.py
    @desc: 财务数据结构化模型。

    设计：
      - FinancialStatement = 一份文档里的一张报表（资产负债表 / 利润表 / 现金流量表）
        + 报告期（年度/季度/月度）+ 主体。
      - FinancialFact = 单个科目在该期的数字。value 始终存"元"，单位归一化到 statement
        头上记录。
      - 这两张表与 Paragraph / 向量召回并存：向量库继续做"找到相关段落"，
        FinancialFact 表做"按主体+期间+科目精确取数"。
      - 抽取由 services/financial_extractor.py 完成（纯规则 + 别名表）；本模型不
        承载业务逻辑，只是结构化"事实表"。
"""
import uuid_utils.compat as uuid
from django.db import models

from common.mixins.app_model_mixin import AppModelMixin
from knowledge.models.knowledge import Document


class StatementType(models.TextChoices):
    BALANCE_SHEET = 'balance_sheet', '资产负债表'
    INCOME_STATEMENT = 'income_statement', '利润表'
    CASH_FLOW = 'cash_flow', '现金流量表'


class PeriodType(models.TextChoices):
    ANNUAL = 'annual', '年度'
    QUARTER = 'quarter', '季度'
    MONTH = 'month', '月度'


class FinancialStatement(AppModelMixin):
    """一份财务报表 = 一个文档里某一张表 + 某一期数据。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False, verbose_name="主键id")
    document = models.ForeignKey(
        Document, on_delete=models.DO_NOTHING, db_constraint=False, verbose_name="来源文档"
    )
    statement_type = models.CharField(
        max_length=32, choices=StatementType.choices, db_index=True, verbose_name="报表类型"
    )
    period = models.CharField(
        max_length=32, db_index=True,
        verbose_name="报告期",
        help_text="规范字符串：年度 '2024' / 季度 '2024Q1' / 月度 '2024-03'",
    )
    period_type = models.CharField(
        max_length=16, choices=PeriodType.choices, default=PeriodType.ANNUAL,
        verbose_name="期间粒度",
    )
    entity_name = models.CharField(
        max_length=256, db_index=True, default='', verbose_name="主体名称",
        help_text="如：盐城市保安服务有限公司"
    )
    unit = models.CharField(
        max_length=16, default='元', verbose_name="单位",
        help_text="表头声明的单位：元 / 万元 / 千元。value 字段值是按这个单位的原始数",
    )
    raw_table_md = models.TextField(
        blank=True, default='', verbose_name="原始 markdown 表格",
        help_text="抽取时保留的原文，便于回溯 / 重抽 / 人工校对",
    )
    extractor_version = models.CharField(
        max_length=32, default='v1.0', verbose_name="抽取器版本",
        help_text="便于以后批量重抽：新版本上线后只重跑老版本数据",
    )

    class Meta:
        db_table = "financial_statement"
        indexes = [
            models.Index(fields=['document', 'statement_type', 'period']),
            models.Index(fields=['entity_name', 'statement_type', 'period']),
        ]


class FinancialFact(AppModelMixin):
    """单一科目数字。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False, verbose_name="主键id")
    statement = models.ForeignKey(
        FinancialStatement, on_delete=models.CASCADE, db_constraint=False,
        related_name='facts', verbose_name="所属报表",
    )
    # 原始行首
    line_item = models.CharField(
        max_length=128, verbose_name="科目（原文）",
        help_text="表里行首文字，可能带缩进 / 序号 / '其中：' 等",
    )
    # 归一后的科目名（去掉别名 / 后缀），便于跨文档查询
    line_item_normalized = models.CharField(
        max_length=128, db_index=True, default='',
        verbose_name="科目（归一化）",
        help_text="对照别名表后的标准名：'货币资金' / '应收账款' / '主营业务收入' …",
    )
    value = models.DecimalField(
        max_digits=22, decimal_places=4, null=True,
        verbose_name="数值",
        help_text="按 statement.unit 单位存储。NULL = 表格里就是空 / '-'",
    )
    parent_line_item = models.CharField(
        max_length=128, blank=True, default='',
        verbose_name="父级科目",
        help_text="如 '货币资金' 的父级是 '流动资产合计'。用于辅助识别明细/合计关系",
    )
    indent_level = models.IntegerField(
        default=0, verbose_name="缩进层级",
        help_text="0=顶层科目，1+=明细。从原始行首空格 / 缩进推断",
    )

    class Meta:
        db_table = "financial_fact"
        indexes = [
            models.Index(fields=['statement', 'line_item_normalized']),
            models.Index(fields=['line_item_normalized']),
        ]

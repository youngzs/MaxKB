# Generated for Phase 3 — Financial structured data + deterministic calculation.

import uuid_utils.compat as uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0008_document_sensitivity_level'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinancialStatement',
            fields=[
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
                ('id', models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False, verbose_name='主键id')),
                ('statement_type', models.CharField(
                    choices=[('balance_sheet', '资产负债表'), ('income_statement', '利润表'), ('cash_flow', '现金流量表')],
                    db_index=True, max_length=32, verbose_name='报表类型'
                )),
                ('period', models.CharField(
                    db_index=True, help_text="规范字符串：年度 '2024' / 季度 '2024Q1' / 月度 '2024-03'",
                    max_length=32, verbose_name='报告期'
                )),
                ('period_type', models.CharField(
                    choices=[('annual', '年度'), ('quarter', '季度'), ('month', '月度')],
                    default='annual', max_length=16, verbose_name='期间粒度'
                )),
                ('entity_name', models.CharField(
                    db_index=True, default='', help_text='如：盐城市保安服务有限公司',
                    max_length=256, verbose_name='主体名称'
                )),
                ('unit', models.CharField(
                    default='元', help_text='表头声明的单位：元 / 万元 / 千元。value 字段值是按这个单位的原始数',
                    max_length=16, verbose_name='单位'
                )),
                ('raw_table_md', models.TextField(
                    blank=True, default='', help_text='抽取时保留的原文，便于回溯 / 重抽 / 人工校对',
                    verbose_name='原始 markdown 表格'
                )),
                ('extractor_version', models.CharField(
                    default='v1.0', help_text='便于以后批量重抽：新版本上线后只重跑老版本数据',
                    max_length=32, verbose_name='抽取器版本'
                )),
                ('document', models.ForeignKey(
                    db_constraint=False, on_delete=models.deletion.DO_NOTHING,
                    to='knowledge.document', verbose_name='来源文档'
                )),
            ],
            options={
                'db_table': 'financial_statement',
                'indexes': [
                    models.Index(fields=['document', 'statement_type', 'period'],
                                 name='fin_stmt_doc_type_period_idx'),
                    models.Index(fields=['entity_name', 'statement_type', 'period'],
                                 name='fin_stmt_ent_type_period_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='FinancialFact',
            fields=[
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
                ('id', models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False, verbose_name='主键id')),
                ('line_item', models.CharField(
                    help_text="表里行首文字，可能带缩进 / 序号 / '其中：' 等",
                    max_length=128, verbose_name='科目（原文）'
                )),
                ('line_item_normalized', models.CharField(
                    db_index=True, default='',
                    help_text="对照别名表后的标准名：'货币资金' / '应收账款' / '主营业务收入' …",
                    max_length=128, verbose_name='科目（归一化）'
                )),
                ('value', models.DecimalField(
                    decimal_places=4, max_digits=22, null=True,
                    help_text="按 statement.unit 单位存储。NULL = 表格里就是空 / '-'",
                    verbose_name='数值'
                )),
                ('parent_line_item', models.CharField(
                    blank=True, default='',
                    help_text="如 '货币资金' 的父级是 '流动资产合计'。用于辅助识别明细/合计关系",
                    max_length=128, verbose_name='父级科目'
                )),
                ('indent_level', models.IntegerField(
                    default=0,
                    help_text='0=顶层科目，1+=明细。从原始行首空格 / 缩进推断',
                    verbose_name='缩进层级'
                )),
                ('statement', models.ForeignKey(
                    db_constraint=False, on_delete=models.deletion.CASCADE,
                    related_name='facts', to='knowledge.financialstatement', verbose_name='所属报表'
                )),
            ],
            options={
                'db_table': 'financial_fact',
                'indexes': [
                    models.Index(fields=['statement', 'line_item_normalized'],
                                 name='fin_fact_stmt_norm_idx'),
                    models.Index(fields=['line_item_normalized'],
                                 name='fin_fact_norm_idx'),
                ],
            },
        ),
    ]

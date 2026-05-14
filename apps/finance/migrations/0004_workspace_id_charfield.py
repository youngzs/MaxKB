# coding=utf-8
"""
    @project: MaxKB
    @file: 0004_workspace_id_charfield.py
    @desc: Convert finance.*.workspace_id from UUIDField to CharField(max_length=64)
           to align with the rest of MaxKB which stores workspace IDs as opaque
           strings (e.g. the literal 'default' for the singleton workspace).

           Existing rows whose workspace_id were UUIDs cast cleanly to text via
           PostgreSQL's USING ::text clause; Django emits this automatically
           when altering UUID -> varchar.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0003_materialstask'),
    ]

    operations = [
        migrations.AlterField(
            model_name='financeproject',
            name='workspace_id',
            field=models.CharField(db_index=True, max_length=64, verbose_name='工作空间id'),
        ),
        migrations.AlterField(
            model_name='financeauditlog',
            name='workspace_id',
            field=models.CharField(db_index=True, max_length=64, verbose_name='工作空间id'),
        ),
        migrations.AlterField(
            model_name='documenttemplate',
            name='workspace_id',
            field=models.CharField(db_index=True, max_length=64, verbose_name='工作空间id'),
        ),
        migrations.AlterField(
            model_name='documentgeneration',
            name='workspace_id',
            field=models.CharField(db_index=True, max_length=64, verbose_name='工作空间id'),
        ),
        migrations.AlterField(
            model_name='materialstask',
            name='workspace_id',
            field=models.CharField(db_index=True, max_length=64, verbose_name='工作空间id'),
        ),
    ]

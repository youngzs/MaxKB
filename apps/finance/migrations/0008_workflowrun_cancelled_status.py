# Generated for MaxKB Finance — Gate 8 Track B
# Hand-written (same reason as 0005/0006/0007: Windows dev cannot import the
# full Django app stack to run makemigrations).
#
# Adds the 'cancelled' choice to WorkflowRun.status. This is a no-op at the
# database level (the column is already a varchar(20) with no DB-side CHECK
# constraint), but Django tracks `choices` in migration state, so this keeps
# `makemigrations --check` clean for anyone who can run it.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0007_workflow_run'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflowrun',
            name='status',
            field=models.CharField(
                choices=[
                    ('queued', '排队中'),
                    ('running', '运行中'),
                    ('succeeded', '成功'),
                    ('failed', '失败'),
                    ('retrying', '重试中'),
                    ('cancelled', '已取消'),
                ],
                default='queued',
                max_length=20,
                verbose_name='状态',
            ),
        ),
    ]

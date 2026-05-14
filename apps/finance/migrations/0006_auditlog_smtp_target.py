# Generated for MaxKB Finance — Gate 5 Track C
# Hand-written (same reason as 0005_smtp_email.py: Windows dev cannot import
# the full Django app stack to run makemigrations). The change is a pure
# choices update on FinanceAuditLog.target_type — no DB-level alteration is
# required for PostgreSQL CharField, but Django needs the migration recorded
# so checks/migrate don't complain about model-state drift.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0005_smtp_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='financeauditlog',
            name='target_type',
            field=models.CharField(
                choices=[
                    ('PROJECT', 'project'),
                    ('MATERIALS_TASK', 'materials_task'),
                    ('DOC_TEMPLATE', 'doc_template'),
                    ('DOC_GENERATION', 'doc_generation'),
                    ('SMTP_CONFIG', 'smtp_config'),
                    ('OTHER', 'other'),
                ],
                max_length=32,
                verbose_name='对象类型',
            ),
        ),
    ]

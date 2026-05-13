# Generated for Gate 2 Track C — Document sensitivity classification.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0007_remove_knowledgeworkflowversion_workflow_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='sensitivity_level',
            field=models.CharField(
                choices=[
                    ('public', '公开'),
                    ('internal', '内部'),
                    ('confidential', '机密'),
                    ('secret', '涉密'),
                ],
                db_index=True,
                default='internal',
                help_text='Document sensitivity level — hard-controls external sharing eligibility.',
                max_length=20,
                verbose_name='敏感等级',
            ),
        ),
    ]

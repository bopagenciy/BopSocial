# Generated for BS-4H Grounded AI Executive Narrative & Recommendation Layer

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('social_stats', '0079_executivereport'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExecutiveNarrative',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(default='es', max_length=10)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('GENERATED', 'Generated'), ('VALIDATED', 'Validated'), ('REJECTED', 'Rejected'), ('FAILED', 'Failed')], db_index=True, default='DRAFT', max_length=20)),
                ('provider', models.CharField(default='fake', max_length=50)),
                ('model_name', models.CharField(default='stub-model-v1', max_length=100)),
                ('prompt_version', models.CharField(default='bs4h-prompt-v1', max_length=50)),
                ('context_schema_version', models.CharField(default='bs4h-context-v1', max_length=50)),
                ('source_hash', models.CharField(db_index=True, max_length=64)),
                ('context_hash', models.CharField(db_index=True, max_length=64)),
                ('narrative_json', models.JSONField(default=dict)),
                ('rendered_text', models.TextField(blank=True, default='')),
                ('validation_status', models.CharField(default='PENDING', max_length=20)),
                ('validation_results', models.JSONField(blank=True, default=dict)),
                ('generated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executive_narratives', to='social_stats.client')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_executive_narratives', to=settings.AUTH_USER_MODEL)),
                ('executive_report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='narratives', to='social_stats.executivereport')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['client', '-created_at'], name='social_stat_client__fa4854_idx'),
                    models.Index(fields=['executive_report', '-created_at'], name='social_stat_executi_3861db_idx'),
                    models.Index(fields=['client', 'status'], name='social_stat_client__0911b6_idx'),
                    models.Index(fields=['source_hash'], name='social_stat_source__b88bca_idx'),
                    models.Index(fields=['context_hash'], name='social_stat_context_a47028_idx'),
                ],
            },
        ),
    ]

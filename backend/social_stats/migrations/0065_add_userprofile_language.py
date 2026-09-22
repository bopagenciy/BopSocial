# Generated for Phase BS-2.0 Internationalization Foundation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social_stats', '0064_rename_gateway_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='language',
            field=models.CharField(
                choices=[('en', 'English'), ('es', 'Spanish')],
                default='en',
                max_length=10,
            ),
        ),
    ]

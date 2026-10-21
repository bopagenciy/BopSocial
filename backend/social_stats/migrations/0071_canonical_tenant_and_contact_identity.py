# Generated manually for BOP-CONV-B1A Canonical Identity Foundation
import uuid
from django.db import migrations, models


def backfill_canonical_identities(apps, schema_editor):
    Client = apps.get_model('social_stats', 'Client')
    WhatsAppContact = apps.get_model('social_stats', 'WhatsAppContact')

    # Assign deterministic, stable, unique UUIDv4 to any existing Client
    for client in Client.objects.all():
        if not client.bop_organization_id:
            client.bop_organization_id = uuid.uuid4()
            client.save(update_fields=['bop_organization_id'])

    # Assign deterministic, stable, unique UUIDv4 to any existing WhatsAppContact
    for contact in WhatsAppContact.objects.all():
        if not contact.bop_contact_id:
            contact.bop_contact_id = uuid.uuid4()
            contact.save(update_fields=['bop_contact_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('social_stats', '0070_alter_client_currency'),
    ]

    operations = [
        # Step 1: Add bop_organization_id with null=True
        migrations.AddField(
            model_name='client',
            name='bop_organization_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                editable=False,
                db_index=True,
                help_text="Canonical Bop Universe organization identifier (UUIDv4).",
            ),
        ),
        # Step 2: Add bop_contact_id with null=True
        migrations.AddField(
            model_name='whatsappcontact',
            name='bop_contact_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                editable=False,
                db_index=True,
                help_text="Canonical Bop Universe contact identifier (UUIDv4).",
            ),
        ),
        # Step 3: Run data backfill for existing rows
        migrations.RunPython(
            backfill_canonical_identities,
            reverse_code=migrations.RunPython.noop,
        ),
        # Step 4: Alter bop_organization_id to unique=True, null=False, default=uuid.uuid4
        migrations.AlterField(
            model_name='client',
            name='bop_organization_id',
            field=models.UUIDField(
                default=uuid.uuid4,
                unique=True,
                editable=False,
                db_index=True,
                help_text="Canonical Bop Universe organization identifier (UUIDv4).",
            ),
        ),
        # Step 5: Alter bop_contact_id to unique=True, null=False, default=uuid.uuid4
        migrations.AlterField(
            model_name='whatsappcontact',
            name='bop_contact_id',
            field=models.UUIDField(
                default=uuid.uuid4,
                unique=True,
                editable=False,
                db_index=True,
                help_text="Canonical Bop Universe contact identifier (UUIDv4).",
            ),
        ),
    ]

# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Bop Social Security Hardening — Legacy Media Migration (SEC-01)
# ============================================================================
"""
Management command: python manage.py migrate_tenant_media [--dry-run] [--client=<id>]

Safely and idempotently partitions legacy media assets into tenant-isolated
directories:
  From: media_assets/%Y/%m/<filename>
  To:   media_assets/tenant_<client_id>/%Y/%m/<filename>

Rollback guidance:
  The command records every path update. If a rollback is ever needed, the original
  paths are logged and can be restored using the emitted JSON manifest.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from social_stats.models import MediaAsset

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Idempotently partition legacy MediaAsset files into tenant-scoped directories.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the migration without modifying files or database records.',
        )
        parser.add_argument(
            '--client',
            type=int,
            default=None,
            help='Migrate media for a specific client ID only.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        cid = options['client']

        media_root = os.path.abspath(str(settings.MEDIA_ROOT))
        self.stdout.write(f"Media root: {media_root}")
        if dry_run:
            self.stdout.write(self.style.WARNING("--- RUNNING IN DRY-RUN MODE (No changes will be applied) ---"))

        qs = MediaAsset.objects.all().order_by('id')
        if cid:
            qs = qs.filter(client_id=cid)

        total = qs.count()
        migrated = 0
        skipped = 0
        errors = 0
        manifest = []

        for asset in qs:
            client_id = asset.client_id or 'shared'
            expected_prefix = f"media_assets/tenant_{client_id}/"

            # Check if already partitioned
            if asset.file and asset.file.name.startswith(expected_prefix):
                skipped += 1
                continue

            if not asset.file or not asset.file.name:
                skipped += 1
                continue

            old_file_name = asset.file.name
            old_file_path = os.path.join(media_root, old_file_name)

            # Determine timestamp
            dt = asset.created_at or timezone.now()
            file_basename = os.path.basename(old_file_name)
            new_file_name = f"media_assets/tenant_{client_id}/{dt.year:04d}/{dt.month:02d}/{file_basename}"
            new_file_path = os.path.join(media_root, new_file_name)

            # Thumbnail handling
            old_thumb_name = asset.thumbnail.name if asset.thumbnail else ''
            new_thumb_name = ''
            if old_thumb_name and not old_thumb_name.startswith(f"media_assets/thumbs/tenant_{client_id}/"):
                thumb_basename = os.path.basename(old_thumb_name)
                new_thumb_name = f"media_assets/thumbs/tenant_{client_id}/{dt.year:04d}/{dt.month:02d}/{thumb_basename}"

            record = {
                'asset_id': asset.id,
                'client_id': client_id,
                'old_file': old_file_name,
                'new_file': new_file_name,
                'old_thumb': old_thumb_name,
                'new_thumb': new_thumb_name,
            }
            manifest.append(record)

            self.stdout.write(f"Asset #{asset.id} (Client #{client_id}): {old_file_name} -> {new_file_name}")

            if not dry_run:
                try:
                    # Move main file if exists on disk
                    if os.path.exists(old_file_path):
                        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
                        shutil.copy2(old_file_path, new_file_path)
                        # Remove old after copy
                        try:
                            os.remove(old_file_path)
                        except OSError:
                            pass

                    # Move thumbnail if exists
                    if old_thumb_name and new_thumb_name:
                        old_thumb_path = os.path.join(media_root, old_thumb_name)
                        new_thumb_path = os.path.join(media_root, new_thumb_name)
                        if os.path.exists(old_thumb_path):
                            os.makedirs(os.path.dirname(new_thumb_path), exist_ok=True)
                            shutil.copy2(old_thumb_path, new_thumb_path)
                            try:
                                os.remove(old_thumb_path)
                            except OSError:
                                pass

                    # Update database row
                    asset.file.name = new_file_name
                    if new_thumb_name:
                        asset.thumbnail.name = new_thumb_name
                    asset.save(update_fields=['file', 'thumbnail'])
                    migrated += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Error migrating asset #{asset.id}: {e}"))
                    errors += 1
            else:
                migrated += 1

        summary = (
            f"\nMigration Summary:\n"
            f"  Total records: {total}\n"
            f"  Eligible for migration: {migrated}\n"
            f"  Already partitioned / skipped: {skipped}\n"
            f"  Errors: {errors}\n"
        )
        self.stdout.write(self.style.SUCCESS(summary))

        if not dry_run and manifest:
            manifest_path = os.path.join(media_root, f"migration_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            try:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)
                self.stdout.write(f"Rollback manifest saved to: {manifest_path}")
            except Exception as e:
                self.stderr.write(f"Could not save manifest: {e}")

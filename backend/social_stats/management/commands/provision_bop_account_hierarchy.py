import uuid
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import connection, transaction
from social_stats.models import Client, UserProfile
from social_stats.marketplace_models import Agency, AgencyMembership, AgencyClientRelation

CANONICAL_BOP_AGENCIA_SLUG = 'bop-agencia'
CANONICAL_BOP_CLIENT_ID = 3
CANONICAL_BOP_ORG_UUID = uuid.UUID('d4c60c86-30a4-4360-8464-81c0af1d813c')
SUPERADMIN_EMAIL = 'bopsoluciones@gmail.com'
AGENCY_OWNER_EMAIL = 'bopagencia@gmail.com'


class Command(BaseCommand):
    help = "Idempotently provision/reconcile the canonical BOP Social account hierarchy (BS-8B)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate execution and display changes without persisting to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        # 1. Enforce canonical PostgreSQL database only
        if connection.vendor != 'postgresql':
            raise CommandError(
                f"CANONICAL DATABASE GUARD: Expected PostgreSQL, but active engine is '{connection.vendor}'. "
                "Do NOT run this command against SQLite or non-canonical databases."
            )

        self.stdout.write(self.style.MIGRATE_HEADING("=================================================="))
        self.stdout.write(self.style.MIGRATE_HEADING("  BOP SOCIAL — CANONICAL ACCOUNT PROVISIONING    "))
        self.stdout.write(self.style.MIGRATE_HEADING("=================================================="))
        self.stdout.write(f"Database Engine : {connection.vendor} (canonical PostgreSQL verified)")
        self.stdout.write(f"Dry Run Mode    : {dry_run}\n")

        with transaction.atomic():
            # 2. Verify pre-existing canonical Agency and Client #3
            self.stdout.write(self.style.HTTP_INFO("[1/4] Verifying canonical Bop Agencia records..."))

            agency = Agency.objects.filter(slug=CANONICAL_BOP_AGENCIA_SLUG).first()
            if not agency:
                raise CommandError(
                    f"MISSING CANONICAL AGENCY: Agency with slug '{CANONICAL_BOP_AGENCIA_SLUG}' not found in PostgreSQL. "
                    "Aborting as required by specification."
                )

            client_3 = Client.objects.filter(id=CANONICAL_BOP_CLIENT_ID).first()
            if not client_3:
                raise CommandError(
                    f"MISSING CANONICAL CLIENT: Client #{CANONICAL_BOP_CLIENT_ID} not found in PostgreSQL. "
                    "Aborting as required by specification."
                )

            if client_3.bop_organization_id != CANONICAL_BOP_ORG_UUID:
                raise CommandError(
                    f"ORGANIZATION ID MISMATCH: Client #3 has bop_organization_id={client_3.bop_organization_id}, "
                    f"expected {CANONICAL_BOP_ORG_UUID}."
                )

            self.stdout.write(self.style.SUCCESS(
                f"  -> Agency verified: ID {agency.id} ('{agency.name}', slug='{agency.slug}')"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"  -> Client #3 verified: ID {client_3.id} ('{client_3.company}', bop_org_id={client_3.bop_organization_id})\n"
            ))

            # 3. Provision / Reconcile Super Admin (bopsoluciones@gmail.com)
            self.stdout.write(self.style.HTTP_INFO("[2/4] Provisioning / Reconciling Global Super Admin..."))
            super_user, super_created = User.objects.get_or_create(
                username=SUPERADMIN_EMAIL,
                defaults={
                    'email': SUPERADMIN_EMAIL,
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                }
            )

            if super_created:
                super_user.set_unusable_password()
                super_user.save()
                self.stdout.write(self.style.SUCCESS(f"  -> Created User: {super_user.email} (ID: {super_user.id})"))
            else:
                updated_fields = []
                if super_user.email != SUPERADMIN_EMAIL:
                    super_user.email = SUPERADMIN_EMAIL
                    updated_fields.append('email')
                if not super_user.is_staff:
                    super_user.is_staff = True
                    updated_fields.append('is_staff')
                if not super_user.is_superuser:
                    super_user.is_superuser = True
                    updated_fields.append('is_superuser')
                if not super_user.is_active:
                    super_user.is_active = True
                    updated_fields.append('is_active')
                if updated_fields:
                    super_user.save(update_fields=updated_fields)
                    self.stdout.write(self.style.SUCCESS(f"  -> Reconciled User: {super_user.email} (updated: {', '.join(updated_fields)})"))
                else:
                    self.stdout.write(f"  -> User unchanged: {super_user.email} (ID: {super_user.id})")

            # Password check without exposing secrets
            super_pwd_status = "USABLE" if super_user.has_usable_password() else "UNUSABLE (SETUP REQUIRED)"
            self.stdout.write(f"  -> Password Status: {super_pwd_status}")

            # Reconcile UserProfile for Super Admin
            super_profile, prof_created = UserProfile.objects.get_or_create(
                user=super_user,
                defaults={
                    'role': 'superadmin',
                    'account_type': 'legacy',
                    'client': None,
                    'primary_agency': None,
                    'default_workspace': None,
                    'email_verified': True,
                    'terms_accepted': True,
                }
            )
            if not prof_created:
                prof_updates = []
                if super_profile.role != 'superadmin':
                    super_profile.role = 'superadmin'
                    prof_updates.append('role')
                if super_profile.client is not None:
                    super_profile.client = None
                    prof_updates.append('client')
                if super_profile.primary_agency is not None:
                    super_profile.primary_agency = None
                    prof_updates.append('primary_agency')
                if super_profile.default_workspace is not None:
                    super_profile.default_workspace = None
                    prof_updates.append('default_workspace')
                if not super_profile.email_verified:
                    super_profile.email_verified = True
                    prof_updates.append('email_verified')
                if not super_profile.terms_accepted:
                    super_profile.terms_accepted = True
                    prof_updates.append('terms_accepted')
                if prof_updates:
                    super_profile.save(update_fields=prof_updates)
                    self.stdout.write(self.style.SUCCESS(f"  -> Reconciled UserProfile: (updated: {', '.join(prof_updates)})"))
                else:
                    self.stdout.write(f"  -> UserProfile unchanged: role='{super_profile.role}'")

            # Ensure superadmin has no agency membership
            deleted_memberships, _ = AgencyMembership.objects.filter(user=super_user).delete()
            if deleted_memberships:
                self.stdout.write(self.style.WARNING(f"  -> Removed {deleted_memberships} detached AgencyMembership record(s) from superadmin."))
            self.stdout.write("")

            # 4. Provision / Reconcile Bop Agencia Owner (bopagencia@gmail.com)
            self.stdout.write(self.style.HTTP_INFO("[3/4] Provisioning / Reconciling Bop Agencia Owner..."))
            agency_user, agency_user_created = User.objects.get_or_create(
                username=AGENCY_OWNER_EMAIL,
                defaults={
                    'email': AGENCY_OWNER_EMAIL,
                    'is_staff': False,
                    'is_superuser': False,
                    'is_active': True,
                }
            )

            if agency_user_created:
                agency_user.set_unusable_password()
                agency_user.save()
                self.stdout.write(self.style.SUCCESS(f"  -> Created User: {agency_user.email} (ID: {agency_user.id})"))
            else:
                updated_fields = []
                if agency_user.email != AGENCY_OWNER_EMAIL:
                    agency_user.email = AGENCY_OWNER_EMAIL
                    updated_fields.append('email')
                if agency_user.is_staff:
                    agency_user.is_staff = False
                    updated_fields.append('is_staff')
                if agency_user.is_superuser:
                    agency_user.is_superuser = False
                    updated_fields.append('is_superuser')
                if not agency_user.is_active:
                    agency_user.is_active = True
                    updated_fields.append('is_active')
                if updated_fields:
                    agency_user.save(update_fields=updated_fields)
                    self.stdout.write(self.style.SUCCESS(f"  -> Reconciled User: {agency_user.email} (updated: {', '.join(updated_fields)})"))
                else:
                    self.stdout.write(f"  -> User unchanged: {agency_user.email} (ID: {agency_user.id})")

            agency_pwd_status = "USABLE" if agency_user.has_usable_password() else "UNUSABLE (SETUP REQUIRED)"
            self.stdout.write(f"  -> Password Status: {agency_pwd_status}")

            # Reconcile UserProfile for Bop Agencia Owner
            agency_profile, a_prof_created = UserProfile.objects.get_or_create(
                user=agency_user,
                defaults={
                    'role': 'client',
                    'account_type': 'agency_member',
                    'primary_agency': agency,
                    'client': client_3,
                    'default_workspace': client_3,
                    'email_verified': True,
                    'terms_accepted': True,
                }
            )
            if not a_prof_created:
                a_prof_updates = []
                if agency_profile.role != 'client':
                    agency_profile.role = 'client'
                    a_prof_updates.append('role')
                if agency_profile.account_type != 'agency_member':
                    agency_profile.account_type = 'agency_member'
                    a_prof_updates.append('account_type')
                if agency_profile.primary_agency_id != agency.id:
                    agency_profile.primary_agency = agency
                    a_prof_updates.append('primary_agency')
                if agency_profile.client_id != client_3.id:
                    agency_profile.client = client_3
                    a_prof_updates.append('client')
                if agency_profile.default_workspace_id != client_3.id:
                    agency_profile.default_workspace = client_3
                    a_prof_updates.append('default_workspace')
                if not agency_profile.email_verified:
                    agency_profile.email_verified = True
                    a_prof_updates.append('email_verified')
                if not agency_profile.terms_accepted:
                    agency_profile.terms_accepted = True
                    a_prof_updates.append('terms_accepted')
                if a_prof_updates:
                    agency_profile.save(update_fields=a_prof_updates)
                    self.stdout.write(self.style.SUCCESS(f"  -> Reconciled UserProfile: (updated: {', '.join(a_prof_updates)})"))
                else:
                    self.stdout.write(f"  -> UserProfile unchanged: role='{agency_profile.role}', primary_agency='{agency.slug}'")

            # Reconcile AgencyMembership
            membership, m_created = AgencyMembership.objects.get_or_create(
                agency=agency,
                user=agency_user,
                defaults={
                    'role': 'owner',
                    'is_active': True,
                }
            )
            if m_created:
                self.stdout.write(self.style.SUCCESS(f"  -> Created AgencyMembership: ID {membership.id} (agency='{agency.slug}', role='owner')"))
            else:
                m_updates = []
                if membership.role != 'owner':
                    membership.role = 'owner'
                    m_updates.append('role')
                if not membership.is_active:
                    membership.is_active = True
                    m_updates.append('is_active')
                if m_updates:
                    membership.save(update_fields=m_updates)
                    self.stdout.write(self.style.SUCCESS(f"  -> Reconciled AgencyMembership: (updated: {', '.join(m_updates)})"))
                else:
                    self.stdout.write(f"  -> AgencyMembership unchanged: ID {membership.id} (role='{membership.role}', is_active={membership.is_active})")

            # Update Agency owner_user if not already set to bopagencia@gmail.com
            if agency.owner_user_id != agency_user.id:
                agency.owner_user = agency_user
                agency.save(update_fields=['owner_user'])
                self.stdout.write(self.style.SUCCESS(f"  -> Reconciled Agency.owner_user -> {agency_user.email}"))
            else:
                self.stdout.write(f"  -> Agency.owner_user already set to {agency_user.email}")

            # Ensure active AgencyClientRelation for Client #3
            relation, rel_created = AgencyClientRelation.objects.get_or_create(
                agency=agency,
                client=client_3,
                defaults={
                    'status': 'active',
                    'initiated_by': 'agency',
                    'initiated_by_user': agency_user,
                }
            )
            if rel_created:
                self.stdout.write(self.style.SUCCESS(f"  -> Created AgencyClientRelation: ID {relation.id} (Agency #{agency.id} <-> Client #{client_3.id}, status='active')"))
            else:
                rel_updates = []
                if relation.status != 'active':
                    relation.status = 'active'
                    rel_updates.append('status')
                if rel_updates:
                    relation.save(update_fields=rel_updates)
                    self.stdout.write(self.style.SUCCESS(f"  -> Reconciled AgencyClientRelation: (updated: {', '.join(rel_updates)})"))
                else:
                    self.stdout.write(f"  -> AgencyClientRelation unchanged: ID {relation.id} (status='{relation.status}')")

            self.stdout.write("")

            # 5. Integrity & Duplicate Verification
            self.stdout.write(self.style.HTTP_INFO("[4/4] Verifying structural integrity..."))
            agency_count = Agency.objects.filter(slug=CANONICAL_BOP_AGENCIA_SLUG).count()
            if agency_count > 1:
                raise CommandError(f"INTEGRITY FAILURE: Duplicate Bop Agencia detected ({agency_count} instances).")

            client_count = Client.objects.filter(id=CANONICAL_BOP_CLIENT_ID).count()
            if client_count > 1:
                raise CommandError(f"INTEGRITY FAILURE: Duplicate Client #{CANONICAL_BOP_CLIENT_ID} detected ({client_count} instances).")

            super_count = User.objects.filter(username=SUPERADMIN_EMAIL).count()
            if super_count > 1:
                raise CommandError(f"INTEGRITY FAILURE: Duplicate Superadmin detected ({super_count} instances).")

            owner_count = User.objects.filter(username=AGENCY_OWNER_EMAIL).count()
            if owner_count > 1:
                raise CommandError(f"INTEGRITY FAILURE: Duplicate Agency Owner detected ({owner_count} instances).")

            self.stdout.write(self.style.SUCCESS("  -> Zero duplicate agencies, clients, or target users."))

            # Dry-run rollback check
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("\n[DRY RUN] All operations validated. Transaction rolled back. No changes were committed."))
            else:
                self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Canonical account hierarchy committed to PostgreSQL successfully."))

        # Post-transaction summary notice on password setup
        self.stdout.write("\n==================================================")
        self.stdout.write("  SECURITY & PASSWORD SUMMARY")
        self.stdout.write("==================================================")
        self.stdout.write(f"1. {SUPERADMIN_EMAIL}: Password setup required = {not super_user.has_usable_password()}")
        self.stdout.write(f"2. {AGENCY_OWNER_EMAIL}: Password setup required = {not agency_user.has_usable_password()}")
        if not super_user.has_usable_password() or not agency_user.has_usable_password():
            self.stdout.write(self.style.NOTICE(
                "\nTo set passwords interactively without logging credentials, execute:\n"
                f"  docker exec -it agencyos-backend-1 python manage.py changepassword {SUPERADMIN_EMAIL}\n"
                f"  docker exec -it agencyos-backend-1 python manage.py changepassword {AGENCY_OWNER_EMAIL}"
            ))
        self.stdout.write("==================================================\n")

"""
Management Command: run_intelligence_automation
Controls execution and dry-run preview for BS-6A Production Intelligence Automation.
"""
from datetime import date
from django.core.management.base import BaseCommand, CommandError

from social_stats.models import Client
from social_stats.analytics.automation import (
    PIPELINE_VERSION,
    evaluate_intelligence_automation_eligibility,
    preview_intelligence_automation,
    execute_intelligence_automation,
)


class Command(BaseCommand):
    help = "Inspects or executes intelligence automation for a client under BS-6A safety boundaries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--client",
            type=int,
            required=True,
            help="Client ID to inspect or automate.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Dry-run preview mode. Strictly zero database writes, zero external calls.",
        )
        parser.add_argument(
            "--period-start",
            type=str,
            default=None,
            help="Reporting period start date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--period-end",
            type=str,
            default=None,
            help="Reporting period end date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--pipeline-version",
            type=str,
            default=PIPELINE_VERSION,
            help="Pipeline version identifier (default: bs6a-v1).",
        )
        parser.add_argument(
            "--explain",
            action="store_true",
            default=False,
            help="Print detailed evaluation metadata, freshness analysis, and artifact reuse decisions.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help=(
                "Operator override for soft operational warnings only (e.g. running MANUAL when config.enabled=False). "
                "CANNOT bypass structural safety gates: client existence, active credentials, "
                "freshness thresholds, provider call budgets, locking, or duplicate active runs."
            ),
        )

    def handle(self, *args, **options):
        client_id = options["client"]
        dry_run = options["dry_run"]
        period_start_str = options["period_start"]
        period_end_str = options["period_end"]
        pipeline_version = options["pipeline_version"]
        explain = options["explain"]
        force = options["force"]

        p_start = date.fromisoformat(period_start_str) if period_start_str else None
        p_end = date.fromisoformat(period_end_str) if period_end_str else None

        client = Client.objects.filter(id=client_id).first()
        if not client:
            raise CommandError(f"Client with ID #{client_id} does not exist.")

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
        self.stdout.write(self.style.MIGRATE_HEADING("BOP SOCIAL — INTELLIGENCE AUTOMATION ORCHESTRATOR"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
        self.stdout.write(f"Client:            #{client.id} {client.name}")
        self.stdout.write(f"Timezone:          {client.timezone or 'America/New_York'}")
        self.stdout.write(f"Requires Approval: {getattr(client, 'requires_approval', True)}")
        self.stdout.write(f"Mode:              {'DRY-RUN (ZERO DB WRITES)' if dry_run else 'LIVE EXECUTION'}")
        self.stdout.write("-" * 70)

        # In BS-6A, only dry-run is authorized
        if not dry_run:
            self.stdout.write(
                self.style.ERROR(
                    "NOTICE: Non-dry execution is restricted in BS-6A phase. Defaulting to safe dry-run preview."
                )
            )
            dry_run = True

        preview = preview_intelligence_automation(
            client_id=client_id,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=pipeline_version,
            trigger_type="MANUAL",
            force=force,
        )

        eligible = preview["eligible"]
        data_eligible = preview.get("data_eligible", True)
        execution_authorized = preview.get("execution_authorized", False)
        status_style = self.style.SUCCESS if eligible else self.style.WARNING

        self.stdout.write(f"Execution Identity:   {preview['execution_identity']}")
        self.stdout.write(f"Pipeline Version:     {preview['pipeline_version']}")
        self.stdout.write(f"Reporting Period:     {preview['period_start']} to {preview['period_end']}")
        self.stdout.write(f"Data Eligible:        {self.style.SUCCESS('YES') if data_eligible else self.style.ERROR('NO')}")
        self.stdout.write(f"Execution Authorized: {self.style.SUCCESS('YES') if execution_authorized else self.style.WARNING('NO (Operator Review / Scheduled Guard Active)')}")
        self.stdout.write(f"Eligibility Status:   {status_style('ELIGIBLE' if eligible else 'BLOCKED')}")
        cov = preview.get("target_period_coverage", {})
        cov_code = cov.get("overall_code", "UNKNOWN")
        cov_pct = cov.get("overall_percent", 0.0)
        cov_thresh = cov.get("threshold_percent", 80)
        cov_style = self.style.SUCCESS if cov.get("is_sufficient") else self.style.ERROR
        self.stdout.write(f"Period Coverage:      {cov_style(f'{cov_code} ({cov_pct:.1f}% / threshold: {cov_thresh}%)')}")
        self.stdout.write(f"Provider Budget:      {preview['provider_call_budget']} max call(s)")
        self.stdout.write("-" * 70)

        if preview["blocking_reasons"]:
            self.stdout.write(self.style.ERROR("Blocking Reasons:"))
            for reason in preview["blocking_reasons"]:
                self.stdout.write(f"  • {reason}")
            self.stdout.write("-" * 70)

        if preview["warnings"]:
            self.stdout.write(self.style.WARNING("Warnings:"))
            for warn in preview["warnings"]:
                self.stdout.write(f"  • {warn}")
            self.stdout.write("-" * 70)

        self.stdout.write("Planned Stages:")
        if preview["planned_stages"]:
            for stg in preview["planned_stages"]:
                self.stdout.write(f"  [>] {stg}")
        else:
            self.stdout.write("  (None — all stages skipped or satisfied)")

        self.stdout.write("\nSkipped Stages / Reuse Decisions:")
        for k, v in preview["reuse_decisions"].items():
            self.stdout.write(f"  [SKIP/REUSE] {k.upper()}: {v}")

        if explain:
            self.stdout.write("\n" + self.style.MIGRATE_LABEL("--- Freshness Details ---"))
            freshness = preview["freshness"]
            self.stdout.write(f"Code:             {freshness.get('code')}")
            self.stdout.write(f"Is Fresh:         {freshness.get('is_fresh')}")
            self.stdout.write(f"Data Age Hours:   {freshness.get('data_age_hours')}")
            self.stdout.write(f"Latest Sync:      {freshness.get('latest_sync_at')}")
            self.stdout.write(f"Latest Snapshot:  {freshness.get('latest_snapshot_date')}")
            self.stdout.write(f"Latest Rollup:    {freshness.get('latest_rollup_date')}")

            self.stdout.write("\n" + self.style.MIGRATE_LABEL("--- Target Period Coverage Details ---"))
            self.stdout.write(f"Overall Code:         {cov.get('overall_code')}")
            self.stdout.write(f"Overall Percent:      {cov.get('overall_percent')}%")
            self.stdout.write(f"Threshold Percent:    {cov.get('threshold_percent')}%")
            self.stdout.write(f"Expected Days:        {cov.get('expected_days')}")
            self.stdout.write(f"Multichannel Complete: {cov.get('is_multichannel_complete')}")
            platforms = cov.get("platforms", {})
            for p_name, p_cov in platforms.items():
                self.stdout.write(f"  [{p_name.upper()}]: {p_cov.get('snapshot_distinct_days')}/{cov.get('expected_days')} days ({p_cov.get('snapshot_coverage_percent')}%) | Mode: {p_cov.get('capability_mode')} | Rollup Days: {p_cov.get('rollup_distinct_days')} | Status: {p_cov.get('coverage_code')}")

            self.stdout.write("\n" + self.style.MIGRATE_LABEL("--- Existing Artifacts ---"))
            artifacts = preview["existing_artifacts"]
            for ak, av in artifacts.items():
                self.stdout.write(f"  {ak}: {av}")

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
        self.stdout.write(self.style.SUCCESS("Dry-run preview completed safely. Zero canonical mutations performed."))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))

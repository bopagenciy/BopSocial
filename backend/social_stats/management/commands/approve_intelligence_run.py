"""
Management Command: approve_intelligence_run
Allows authorized operators to inspect, approve, reject, or resume an intelligence automation run
under BS-6C run-level approval workflow rules.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from social_stats.models import IntelligenceAutomationRun
from social_stats.analytics.automation import (
    ApprovalError,
    AuthorizationError,
    DoubleApprovalError,
    StaleApprovalError,
    approve_intelligence_run,
    reject_intelligence_run,
    resume_approved_intelligence_run,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Approves, rejects, or resumes an intelligence automation run awaiting operator sign-off."

    def add_arguments(self, parser):
        parser.add_argument(
            "--run",
            type=int,
            required=True,
            help="IntelligenceAutomationRun ID to approve or reject.",
        )
        parser.add_argument(
            "--reject",
            action="store_true",
            default=False,
            help="Reject the run instead of approving (transitions to CANCELLED).",
        )
        parser.add_argument(
            "--comment",
            type=str,
            default="",
            help="Optional audit comment explaining the operator decision.",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            default=False,
            help="Immediately initiate controlled resume after approval up to the provider boundary.",
        )
        parser.add_argument(
            "--operator-id",
            type=int,
            default=None,
            help="User ID of the approving operator (defaults to first staff user).",
        )

    def handle(self, *args, **options):
        run_id = options["run"]
        reject_mode = options["reject"]
        comment = options["comment"]
        resume_mode = options["resume"]
        operator_id = options["operator_id"]

        run = IntelligenceAutomationRun.objects.filter(id=run_id).first()
        if not run:
            raise CommandError(f"IntelligenceAutomationRun #{run_id} not found.")

        # Determine operator user
        operator_user = None
        if operator_id:
            operator_user = User.objects.filter(id=operator_id).first()
            if not operator_user:
                raise CommandError(f"Operator User #{operator_id} not found.")
        else:
            # Fallback to first available superuser or staff user
            operator_user = User.objects.filter(is_staff=True).order_by("id").first()
            if not operator_user:
                operator_user = User.objects.filter(is_superuser=True).order_by("id").first()

        if not operator_user:
            raise CommandError("No authorized staff/operator user found in the system.")

        try:
            if reject_mode:
                updated_run = reject_intelligence_run(
                    run_id=run_id,
                    operator_user=operator_user,
                    comment=comment,
                )
                self.stdout.write(self.style.WARNING(
                    f"Run #{updated_run.id} REJECTED by {operator_user.username}. "
                    f"Status: {updated_run.status}, Approval: {updated_run.approval_status}"
                ))
                return

            # Approve Mode
            updated_run = approve_intelligence_run(
                run_id=run_id,
                operator_user=operator_user,
                comment=comment,
            )
            self.stdout.write(self.style.SUCCESS(
                f"Run #{updated_run.id} APPROVED by {operator_user.username}. "
                f"Status: {updated_run.status}, Approval: {updated_run.approval_status}"
            ))

            # Resume Mode if requested
            if resume_mode:
                self.stdout.write("Initiating controlled resume up to provider boundary...")
                resumed_run = resume_approved_intelligence_run(
                    run_id=run_id,
                    operator_user=operator_user,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Run #{resumed_run.id} RESUMED successfully. "
                    f"Status: {resumed_run.status}, Stage: {resumed_run.current_stage}, "
                    f"Provider Calls: {resumed_run.provider_call_count}, "
                    f"Boundary Reached: {resumed_run.metadata.get('provider_boundary_reached', False)}"
                ))

        except (ApprovalError, AuthorizationError, DoubleApprovalError, StaleApprovalError) as exc:
            raise CommandError(f"Approval Workflow Error: {str(exc)}")
        except Exception as exc:
            raise CommandError(f"Unexpected Error during approval operation: {str(exc)}")

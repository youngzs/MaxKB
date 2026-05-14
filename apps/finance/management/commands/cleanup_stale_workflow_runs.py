# coding=utf-8
"""
    @project: MaxKB
    @file:   cleanup_stale_workflow_runs.py
    @desc:   Reap stale finance WorkflowRun rows (Gate 8 Track B).

    A WorkflowRun stuck in 'queued'/'running'/'retrying' long after it
    started usually means the worker died or the broker lost the message.
    This command marks those runs FAILED ('timed out / worker lost') and
    fails the underlying MaterialsTask / DocumentGeneration so the UI
    stops showing an eternal spinner.

    NOT wired to a scheduler — ops can cron it (e.g. every 10 min):

        python apps/manage.py cleanup_stale_workflow_runs
        python apps/manage.py cleanup_stale_workflow_runs --minutes 60
        python apps/manage.py cleanup_stale_workflow_runs --dry-run

    --dry-run lists what *would* be failed (using the read-only
    find_stale_runs helper) without mutating anything.
"""
from django.core.management.base import BaseCommand

from finance.service.workflow_recovery import (
    _IN_FLIGHT_STATUSES,
    auto_fail_stale_runs,
)


class Command(BaseCommand):
    help = (
        'Mark stale finance WorkflowRun rows (stuck queued/running/retrying '
        'past --minutes) as failed, and fail their underlying targets.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=30,
            help='Age threshold in minutes; runs older than this are stale (default 30).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List what would be failed without mutating anything.',
        )

    def handle(self, *args, **options):
        minutes = options.get('minutes') or 30
        if minutes <= 0:
            minutes = 30
        dry_run = bool(options.get('dry_run'))

        if dry_run:
            # Read-only path: enumerate every in-flight run across all
            # workspaces older than the threshold. find_stale_runs is
            # workspace-scoped, so we run the same query directly here.
            from datetime import timedelta

            from django.db.models import Q
            from django.utils import timezone

            from finance.models import WorkflowRun

            cutoff = timezone.now() - timedelta(minutes=minutes)
            qs = (
                WorkflowRun.objects
                .filter(status__in=list(_IN_FLIGHT_STATUSES))
                .filter(
                    Q(started_at__lt=cutoff)
                    | Q(started_at__isnull=True, created_at__lt=cutoff)
                )
                .order_by('created_at')
            )
            rows = list(qs)
            self.stdout.write(
                self.style.WARNING(
                    f'[dry-run] {len(rows)} stale run(s) older than {minutes} min '
                    f'would be failed:'
                )
            )
            for row in rows:
                anchor = row.started_at or row.created_at
                self.stdout.write(
                    f'  - {row.id}  {row.task_name}  status={row.status}  '
                    f'workspace={row.workspace_id}  '
                    f'target={row.target_type}/{row.target_id}  '
                    f'since={anchor.isoformat() if anchor else "?"}'
                )
            if not rows:
                self.stdout.write(self.style.SUCCESS('[dry-run] nothing to do.'))
            return

        count = auto_fail_stale_runs(stale_after_minutes=minutes)
        self.stdout.write(
            self.style.SUCCESS(
                f'Failed {count} stale workflow run(s) older than {minutes} min.'
            )
        )

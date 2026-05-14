# coding=utf-8
"""
    @project: MaxKB
    @file:   signals.py
    @desc:   Django signal receivers for the finance app (Gate 6 Track A2).

    Currently houses one receiver: ``install_workflows_on_migrate`` which
    is wired in ``FinanceConfig.ready()`` to the ``post_migrate`` signal.
    After every migrate cycle (initial deploy or schema upgrade) it
    invokes the ``install_finance_workflows`` management command so the
    preset internal workflows always exist on a fresh database.

    The receiver:
      - is best-effort — any exception is logged and swallowed so a
        broken install candidate never blocks the migrate path
      - is idempotent — the management command uses UUID-5 derived ids
        so re-runs upsert the same rows instead of duplicating
      - runs at ``verbosity=0`` to avoid noisy migrate output in CI
"""
from django.core.management import call_command

from common.utils.logger import maxkb_logger


def install_workflows_on_migrate(sender, **kwargs):
    """
    post_migrate receiver — idempotent install of preset workflows.

    ``sender`` is the AppConfig (``FinanceConfig``) we bound to. Other
    ``post_migrate`` payload keys (``app_config``, ``verbosity``, ``using``,
    ``plan``, ``apps``) are accepted via ``**kwargs`` and ignored.

    Robustness (Gate 7 Track A3):
      - Pre-flight a cheap DB round-trip before invoking the command.
        On a fresh container boot the migrate signal can fire while
        another worker is mid-bootstrap; touching the DB here avoids
        a long timeout inside the management command.
      - Skip when the ``application`` app's required tables aren't
        ready yet (catches an edge case where finance migrates land
        before the ``application`` migrations during a v1→v2 upgrade).
      - All failures swallow into a warning log; no migrate cycle is
        ever blocked by this receiver.
    """
    try:
        # Pre-flight: confirm the Application table the command writes
        # actually exists. ``introspection.table_names`` is a cheap
        # information_schema query and tells us if the migrate cycle
        # that JUST landed included the ``application`` app's tables.
        from django.db import connection

        try:
            with connection.cursor() as cursor:
                table_names = connection.introspection.table_names(cursor)
        except Exception as exc:  # noqa: BLE001
            # DB unreachable / mid-recovery — bail silently. Operators
            # can re-run ``install_finance_workflows`` after boot.
            maxkb_logger.warning(
                f'[finance.signals] install_finance_workflows skipped (DB not ready): {exc}'
            )
            return

        if 'application' not in table_names:
            # The application app's migrations haven't landed yet —
            # this happens on a brand-new database when post_migrate
            # fires for the finance app before the application app's
            # initial migration. Defer; the next migrate cycle (which
            # WILL include the application app since it's in
            # INSTALLED_APPS) re-fires this receiver.
            maxkb_logger.warning(
                '[finance.signals] install_finance_workflows deferred: '
                "the 'application' table does not exist yet"
            )
            return

        call_command('install_finance_workflows', verbosity=0)
    except Exception as exc:  # noqa: BLE001 — never block migrate
        # Use ``warning`` (not ``error``) — a missing workflow file or a
        # transient DB hiccup during the post-migrate hook is not a
        # fatal deployment condition; operators can re-run the command
        # manually later.
        maxkb_logger.warning(
            f'[finance.signals] install_finance_workflows skipped: {exc}'
        )

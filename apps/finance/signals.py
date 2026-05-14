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
    """
    try:
        call_command('install_finance_workflows', verbosity=0)
    except Exception as exc:  # noqa: BLE001 — never block migrate
        # Use ``warning`` (not ``error``) — a missing workflow file or a
        # transient DB hiccup during the post-migrate hook is not a
        # fatal deployment condition; operators can re-run the command
        # manually later.
        maxkb_logger.warning(
            f'[finance.signals] install_finance_workflows skipped: {exc}'
        )

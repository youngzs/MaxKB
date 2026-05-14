from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finance'

    def ready(self):
        """
        Wire the post_migrate signal so preset finance workflows are
        installed automatically after every migration.

        The receiver is imported lazily here (rather than at module level)
        because at ``apps.py`` load time the app registry hasn't fully
        initialised, and importing the signals module pulls in
        ``django.core.management`` which expects a ready apps registry.
        """
        from django.db.models.signals import post_migrate

        from .signals import install_workflows_on_migrate

        # Bind ``sender=self`` so the receiver runs once per migrate cycle
        # for the finance app, not once per app in INSTALLED_APPS. The
        # management command itself is idempotent (UUID-5 derived ids),
        # so a stray duplicate firing would be safe but wasteful.
        post_migrate.connect(install_workflows_on_migrate, sender=self)

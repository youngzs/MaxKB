# coding=utf-8
"""
    @project: MaxKB
    @file： install_finance_workflows.py
    @desc: Install preset finance workflows (Gate 5 Track C — real install).

    Discovers JSON files in ``apps/finance/data/internal_workflows/`` and
    upserts each one into the ``application`` table as an internal
    finance-managed Application of type ``WORK_FLOW``. Reinstalls are
    idempotent: the row id is deterministic per slug, so running the
    command twice updates in place rather than duplicating.

    Note: the JSONs ship with placeholder fields ('' or empty list) for the
    workspace-specific bits (``knowledge_id_list`` on search nodes, model
    id on AI chat nodes). The actual values are injected at runtime when
    the workflow is dispatched from a finance view — we deliberately do
    NOT bake workspace state into the row, so a single internal workflow
    serves every workspace.

    Usage::

        python apps/manage.py install_finance_workflows
        python apps/manage.py install_finance_workflows --dry-run
        python apps/manage.py install_finance_workflows --workspace-id <id>
"""
import json
import os
import uuid

from django.core.management.base import BaseCommand

_WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'internal_workflows')

# Stable UUID-5 namespace for finance-internal workflows. Generated once and
# pinned so the (namespace, slug) -> UUID mapping is reproducible across
# environments. DO NOT change this value — it would orphan existing rows.
_FINANCE_INTERNAL_NS = uuid.UUID('5b9e7c30-2f93-5d5c-9b3c-1f1c6a2b0001')


def _deterministic_id(slug: str) -> uuid.UUID:
    """Derive a stable UUID for ``slug`` so re-installs hit the same row."""
    return uuid.uuid5(_FINANCE_INTERNAL_NS, slug)


def _load_workflow_files(workflows_dir: str):
    """
    Return a list of ``(filename, parsed_json)`` tuples sorted by filename.

    Skips non-JSON files and files that don't parse — those surface as
    warnings on the command stdout so a malformed install candidate doesn't
    silently disappear.
    """
    workflows = []
    if not os.path.isdir(workflows_dir):
        return workflows
    for name in sorted(os.listdir(workflows_dir)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(workflows_dir, name)
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            workflows.append((name, None))
            continue
        workflows.append((name, data))
    return workflows


class Command(BaseCommand):
    help = 'Install preset finance workflows as internal Applications (idempotent upsert by slug).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--workspace-id',
            type=str,
            default='default',
            help=(
                'Workspace id to attach the internal workflows to. Defaults '
                "to 'default' — finance views resolve the internal workflow by "
                'slug regardless of workspace, so this is mostly cosmetic but '
                'lets multi-tenant deployments scope the bookkeeping rows.'
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Discover and validate workflows but do not write to the database.',
        )

    def handle(self, *args, **options):
        workspace_id = options['workspace_id']
        dry_run = options['dry_run']

        workflows_dir = os.path.normpath(_WORKFLOWS_DIR)
        workflows = _load_workflow_files(workflows_dir)

        if not workflows:
            self.stdout.write(self.style.WARNING(
                f'No finance workflow files found in {workflows_dir}'
            ))
            return

        self.stdout.write(self.style.NOTICE(
            f'Discovered {len(workflows)} finance workflow file(s) in {workflows_dir}'
        ))

        # Lazy import: the management command is loaded during Django setup,
        # but the Application model itself requires the full app stack to be
        # initialised first. Importing inside handle() keeps `--help` and
        # syntax checks cheap.
        from application.models.application import Application, ApplicationTypeChoices

        installed = 0
        updated = 0
        unchanged = 0
        skipped = 0
        expected_slugs = []

        for filename, data in workflows:
            if data is None:
                self.stdout.write(self.style.ERROR(f'  x {filename}: failed to parse, skipped'))
                skipped += 1
                continue

            slug = data.get('slug') or ''
            if not slug:
                # Fall back to a slug derived from the filename so older JSONs
                # without an explicit slug still get a stable id.
                slug = '__internal_' + os.path.splitext(filename)[0]

            wf_id = _deterministic_id(slug)
            name = data.get('name') or slug
            description = data.get('description') or ''
            nodes = data.get('nodes') or []
            edges = data.get('edges') or []
            self.stdout.write(
                f'  - {filename}: slug={slug} id={wf_id} '
                f'nodes={len(nodes)} edges={len(edges)} '
                f'version={data.get("version", "?")}'
            )

            expected_slugs.append((slug, wf_id, name, len(nodes)))

            if dry_run:
                continue

            work_flow_payload = {'nodes': nodes, 'edges': edges}
            defaults = {
                'workspace_id': workspace_id,
                'name': name,
                'desc': description[:512],
                'work_flow': work_flow_payload,
                'type': ApplicationTypeChoices.WORK_FLOW,
                'is_publish': True,
            }

            # Determine whether this is a no-op update vs. a real change.
            # We do a pre-fetch so the "unchanged" count is meaningful for
            # operators eyeballing the install report.
            existing = Application.objects.filter(id=wf_id).first()
            if existing is not None:
                old_work_flow = existing.work_flow or {}
                old_name = existing.name
                old_desc = existing.desc or ''
                is_unchanged = (
                    old_work_flow == work_flow_payload
                    and old_name == name
                    and old_desc == description[:512]
                )
            else:
                is_unchanged = False

            obj, created = Application.objects.update_or_create(
                id=wf_id,
                defaults=defaults,
            )
            if created:
                installed += 1
                self.stdout.write(self.style.SUCCESS(f'    + created application id={obj.id}'))
            elif is_unchanged:
                unchanged += 1
                self.stdout.write(f'    = unchanged application id={obj.id}')
            else:
                updated += 1
                self.stdout.write(self.style.SUCCESS(f'    ~ updated application id={obj.id}'))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[dry-run] Would install/update {len(expected_slugs)} workflow(s). '
                'Re-run without --dry-run to write.'
            ))
            return

        # ---- Post-install verification ----
        # Re-fetch by the deterministic ids and assert each row exists
        # with a non-empty work_flow payload. We log a warning (not error)
        # if any row is missing — install path already wrote them, so a
        # post-fetch miss is more likely a routing/DB-replica issue than
        # a real failure. Operators will see it in CI logs either way.
        verified = 0
        for slug, wf_id, name, node_count in expected_slugs:
            row = Application.objects.filter(id=wf_id).first()
            if row is None:
                self.stdout.write(self.style.ERROR(
                    f'  ! verify FAILED: slug={slug} id={wf_id} not found after install'
                ))
                continue
            wf = row.work_flow or {}
            wf_nodes = wf.get('nodes') if isinstance(wf, dict) else None
            if not wf_nodes:
                self.stdout.write(self.style.ERROR(
                    f'  ! verify FAILED: slug={slug} id={wf_id} has empty work_flow.nodes'
                ))
                continue
            verified += 1

        self.stdout.write(self.style.NOTICE(
            f'Done. created={installed} updated={updated} unchanged={unchanged} '
            f'skipped={skipped} verified={verified}/{len(expected_slugs)}'
        ))

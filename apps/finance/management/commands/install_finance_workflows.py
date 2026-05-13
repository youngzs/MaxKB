# coding=utf-8
"""
    @project: MaxKB
    @file： install_finance_workflows.py
    @desc: Skeleton management command. Gate 3 ships only the loading +
    discovery half; the actual install into application's workflow table
    happens in Gate 5 once Track B publishes the docx_render_node and the
    workflow shape is finalised.

    Usage::

        python apps/manage.py install_finance_workflows [--workspace-id <uuid>] [--dry-run]
"""
import json
import os

from django.core.management.base import BaseCommand


_WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'internal_workflows')


class Command(BaseCommand):
    help = 'Install preset finance workflows (Gate 3 SKELETON — logs intent, does not write)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--workspace-id',
            type=str,
            default=None,
            help='Target workspace id; if omitted, all active workspaces are targeted in Gate 5.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be installed without writing (default behaviour today).',
        )

    def handle(self, *args, **options):
        workflows = []
        try:
            workflows_dir = os.path.normpath(_WORKFLOWS_DIR)
            for name in sorted(os.listdir(workflows_dir)):
                if not name.endswith('.json'):
                    continue
                path = os.path.join(workflows_dir, name)
                with open(path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                workflows.append((name, data))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(f'No workflows directory at {_WORKFLOWS_DIR}'))
            return

        self.stdout.write(self.style.NOTICE(
            f'Discovered {len(workflows)} finance workflow file(s) in {_WORKFLOWS_DIR}'
        ))
        for name, data in workflows:
            wf_name = data.get('name', '<unnamed>')
            wf_version = data.get('version', '?')
            node_count = len(data.get('nodes') or [])
            edge_count = len(data.get('edges') or [])
            self.stdout.write(
                f'  - {name}: name={wf_name} version={wf_version} '
                f'nodes={node_count} edges={edge_count}'
            )

        # TODO(Gate 5):
        #   1. Resolve target workspaces (--workspace-id or all active).
        #   2. For each workspace, materialise the workflow JSON:
        #        - substitute knowledge_base_ids placeholder
        #        - resolve workspace's default model id
        #   3. Upsert into application.models.Application as an "internal"
        #      workflow keyed by (workspace_id, internal_name).
        self.stdout.write(self.style.WARNING(
            '[Gate 3 skeleton] No rows written. Real install lands in Gate 5 alongside the docx_render_node.'
        ))

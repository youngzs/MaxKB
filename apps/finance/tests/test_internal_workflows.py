# coding=utf-8
"""
    @project: MaxKB
    @file:   test_internal_workflows.py
    @desc:   Validate the shape of the preset finance workflow JSONs and the
             helpers in install_finance_workflows (Gate 5 Track C).

    Both files must:
      - parse as JSON
      - declare a non-empty ``slug`` and ``name``
      - contain at least one start-node and one end-node
      - reference real workflow node types (search-knowledge-node,
        ai-chat-node, docx-render-node, zip-pack-node, loop-node, etc.)

    The id-derivation helper must be deterministic across runs so the
    upsert in the management command lands on the same row.
"""
import os

from django.test import SimpleTestCase

from finance.management.commands.install_finance_workflows import (
    _deterministic_id,
    _load_workflow_files,
)

_WORKFLOWS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'data', 'internal_workflows')
)


_KNOWN_NODE_TYPES = {
    'base-node',
    'start-node',
    'end-node',
    'search-knowledge-node',
    'ai-chat-node',
    'docx-render-node',
    'loop-node',
    'loop-start-node',
    'loop-break-node',
    'loop-continue-node',
    'zip-pack-node',
}


class PresetWorkflowFilesTest(SimpleTestCase):
    def test_workflows_directory_exists(self):
        self.assertTrue(os.path.isdir(_WORKFLOWS_DIR))

    def test_workflows_parse_and_have_required_top_level_keys(self):
        files = _load_workflow_files(_WORKFLOWS_DIR)
        # Skeleton/empty installs should never happen — Track C ships two.
        self.assertGreaterEqual(len(files), 2)
        for name, data in files:
            with self.subTest(file=name):
                self.assertIsNotNone(data, f'{name} failed to parse')
                self.assertTrue(data.get('slug'), f'{name} missing slug')
                self.assertTrue(data.get('name'), f'{name} missing name')
                self.assertIsInstance(data.get('nodes'), list)
                self.assertIsInstance(data.get('edges'), list)

    def test_each_workflow_has_start_and_end(self):
        for name, data in _load_workflow_files(_WORKFLOWS_DIR):
            with self.subTest(file=name):
                node_types = {n.get('type') for n in (data.get('nodes') or [])}
                self.assertIn('start-node', node_types, f'{name} missing start-node')
                self.assertIn('end-node', node_types, f'{name} missing end-node')

    def test_node_types_are_known(self):
        for name, data in _load_workflow_files(_WORKFLOWS_DIR):
            with self.subTest(file=name):
                for node in data.get('nodes') or []:
                    self.assertIn(
                        node.get('type'),
                        _KNOWN_NODE_TYPES,
                        f'{name}: unexpected node type {node.get("type")!r}',
                    )

    def test_edges_reference_known_node_ids(self):
        for name, data in _load_workflow_files(_WORKFLOWS_DIR):
            with self.subTest(file=name):
                node_ids = {n.get('id') for n in (data.get('nodes') or [])}
                for edge in data.get('edges') or []:
                    src = edge.get('sourceNodeId')
                    dst = edge.get('targetNodeId')
                    self.assertIn(src, node_ids, f'{name}: dangling source {src!r}')
                    self.assertIn(dst, node_ids, f'{name}: dangling target {dst!r}')


class DeterministicIdHelperTest(SimpleTestCase):
    def test_same_slug_yields_same_id(self):
        a = _deterministic_id('__internal_document_generator')
        b = _deterministic_id('__internal_document_generator')
        self.assertEqual(a, b)

    def test_different_slugs_yield_different_ids(self):
        a = _deterministic_id('__internal_document_generator')
        b = _deterministic_id('__internal_materials_packager')
        self.assertNotEqual(a, b)

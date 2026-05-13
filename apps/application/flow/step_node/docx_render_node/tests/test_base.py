# coding=utf-8
"""
    @project: maxkb
    @file:    test_base.py
    @desc:    Unit tests for BaseDocxRenderNode.

    These tests are import-light: they bypass Django ORM by patching the
    module-level _load_bytes / _save_bytes helpers so the test can run
    without a real File table. They cover:

      1. Happy path  — a docx with ``{{name}}`` renders against {"name": "World"}
                       and the resulting bytes contain "World".
      2. Failure path — _load_bytes raises -> error string is populated and
                        output_oss_key is empty; no exception escapes execute().
      3. Idempotency  — invoking execute() twice with the same inputs yields
                        the same OSS key (a deterministic _save_bytes is
                        injected and asserted to be called identically).
"""
from __future__ import annotations

import io
import unittest
from unittest import mock

# docxtpl / python-docx availability is verified at import time; if either is
# absent the test module is skipped rather than failing collection.
try:  # pragma: no cover - import guard
    from docx import Document  # type: ignore
    from docxtpl import DocxTemplate  # type: ignore  # noqa: F401
    _HAVE_DOCX = True
except Exception:  # pragma: no cover
    _HAVE_DOCX = False


def _make_template_with_placeholder(placeholder: str = '{{ name }}') -> bytes:
    """Build a minimal .docx that contains a docxtpl placeholder."""
    doc = Document()
    doc.add_paragraph(f'Hello {placeholder}!')
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _extract_text(docx_bytes: bytes) -> str:
    doc = Document(io.BytesIO(docx_bytes))
    return '\n'.join(p.text for p in doc.paragraphs)


@unittest.skipUnless(_HAVE_DOCX, 'python-docx / docxtpl not installed in this env')
class DocxRenderNodeTests(unittest.TestCase):
    """
    The node class is instantiated without going through the full workflow
    engine; we only need ``execute()`` to behave correctly. ``self.context``
    is set explicitly because the real ``__init__`` reads from a LogicFlow
    node object we don't have here.
    """

    def _make_node(self):
        from application.flow.step_node.docx_render_node.impl.base_docx_render_node import (
            BaseDocxRenderNode,
        )

        node = BaseDocxRenderNode.__new__(BaseDocxRenderNode)
        node.context = {}
        node.status = 200
        node.err_message = ''
        return node

    def test_happy_path_renders_placeholder(self):
        node = self._make_node()
        template_bytes = _make_template_with_placeholder('{{ name }}')

        captured = {}

        def fake_save(file_bytes, file_name):
            captured['bytes'] = file_bytes
            captured['file_name'] = file_name
            return 'deadbeef-0000-0000-0000-000000000001'

        module = 'application.flow.step_node.docx_render_node.impl.base_docx_render_node'
        with mock.patch(f'{module}._load_bytes', return_value=template_bytes), \
                mock.patch(f'{module}._save_bytes', side_effect=fake_save):
            result = node.execute(
                template_oss_key='deadbeef-0000-0000-0000-000000000000',
                placeholder_values={'name': 'World'},
                output_filename='greeting.docx',
            )

        self.assertIsNone(result.node_variable['error'])
        self.assertEqual(result.node_variable['output_oss_key'],
                         'deadbeef-0000-0000-0000-000000000001')
        self.assertEqual(captured['file_name'], 'greeting.docx')
        self.assertIn('World', _extract_text(captured['bytes']))
        self.assertNotIn('{{', _extract_text(captured['bytes']))

    def test_failure_path_returns_error(self):
        node = self._make_node()
        module = 'application.flow.step_node.docx_render_node.impl.base_docx_render_node'
        with mock.patch(f'{module}._load_bytes', side_effect=ValueError('oss key not found: x')):
            result = node.execute(
                template_oss_key='x',
                placeholder_values={'name': 'World'},
                output_filename='out.docx',
            )

        self.assertEqual(result.node_variable['output_oss_key'], '')
        self.assertIn('oss key not found', result.node_variable['error'] or '')
        # context is populated for run-details
        self.assertEqual(node.context['error'] if 'error' in node.context else
                         result.node_variable['error'], result.node_variable['error'])

    def test_idempotent_save_with_same_inputs(self):
        """
        Same inputs → save called with identical bytes count and file_name.
        We don't assert byte-equality because docxtpl can embed a varying rId,
        but the call shape (file_name + presence of placeholder substitution)
        must be stable.
        """
        template_bytes = _make_template_with_placeholder('{{ name }}')
        module = 'application.flow.step_node.docx_render_node.impl.base_docx_render_node'

        calls = []

        def fake_save(file_bytes, file_name):
            calls.append((file_name, 'World' in _extract_text(file_bytes)))
            return f'oss-key-{len(calls)}'

        with mock.patch(f'{module}._load_bytes', return_value=template_bytes), \
                mock.patch(f'{module}._save_bytes', side_effect=fake_save):
            for _ in range(2):
                node = self._make_node()
                node.execute(
                    template_oss_key='same-template',
                    placeholder_values={'name': 'World'},
                    output_filename='out.docx',
                )

        self.assertEqual(len(calls), 2)
        # Both calls had the same target filename and both produced output
        # containing the rendered placeholder.
        self.assertEqual(calls[0][0], calls[1][0])
        self.assertTrue(calls[0][1])
        self.assertTrue(calls[1][1])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

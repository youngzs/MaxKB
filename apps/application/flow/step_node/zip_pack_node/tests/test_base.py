# coding=utf-8
"""
    @project: maxkb
    @file:    test_base.py
    @desc:    Unit tests for BaseZipPackNode.

    These tests bypass Django ORM by patching the module-level _load_bytes /
    _save_bytes helpers so the test can run without a real File table.
    They cover:

      1. Happy path  — three OSS keys → zip with 3 files + README.
      2. Folder grouping — different ``item_folders`` placed under the
                           correct sub-directories.
      3. Missing file — one OSS key resolves to None → ``MISSING_*.txt``
                        marker added, included_count == 2.
      4. Empty input → output_oss_key empty + error populated.
      5. Structure   — README is always present and lists every entry.
"""
from __future__ import annotations

import io
import unittest
import zipfile
from unittest import mock


class ZipPackNodeTests(unittest.TestCase):
    """
    The node class is instantiated without going through the full workflow
    engine; we only need ``execute()`` to behave correctly.
    """

    MODULE = 'application.flow.step_node.zip_pack_node.impl.base_zip_pack_node'

    def _make_node(self):
        from application.flow.step_node.zip_pack_node.impl.base_zip_pack_node import (
            BaseZipPackNode,
        )

        node = BaseZipPackNode.__new__(BaseZipPackNode)
        node.context = {}
        node.status = 200
        node.err_message = ''
        return node

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _payloads(mapping):
        """Return a fake _load_bytes implementation from {key: bytes_or_None}."""
        def fake_load(oss_key):
            return mapping.get(oss_key)
        return fake_load

    @staticmethod
    def _captured_save():
        captured = {}

        def fake_save(file_bytes, file_name):
            captured['bytes'] = file_bytes
            captured['file_name'] = file_name
            return 'deadbeef-0000-0000-0000-000000000001'

        return captured, fake_save

    @staticmethod
    def _open_zip(captured):
        return zipfile.ZipFile(io.BytesIO(captured['bytes']))

    # --------------------------------------------------------------- happy path
    def test_happy_path_three_files(self):
        node = self._make_node()
        captured, fake_save = self._captured_save()
        load = self._payloads({
            'k1': b'AAA',
            'k2': b'BBB',
            'k3': b'CCC',
        })

        with mock.patch(f'{self.MODULE}._load_bytes', side_effect=load), \
                mock.patch(f'{self.MODULE}._save_bytes', side_effect=fake_save):
            result = node.execute(
                document_oss_keys=['k1', 'k2', 'k3'],
                document_names=['a.txt', 'b.txt', 'c.txt'],
                item_folders=[],
                archive_name='bundle.zip',
            )

        self.assertIsNone(result.node_variable['error'])
        self.assertEqual(result.node_variable['included_count'], 3)
        self.assertEqual(result.node_variable['missing'], [])
        self.assertEqual(result.node_variable['output_oss_key'],
                         'deadbeef-0000-0000-0000-000000000001')
        self.assertEqual(captured['file_name'], 'bundle.zip')

        with self._open_zip(captured) as zf:
            names = set(zf.namelist())
            self.assertIn('a.txt', names)
            self.assertIn('b.txt', names)
            self.assertIn('c.txt', names)
            self.assertIn('00_README.md', names)
            # README references each entry
            readme = zf.read('00_README.md').decode('utf-8')
            self.assertIn('a.txt', readme)
            self.assertIn('b.txt', readme)
            self.assertIn('c.txt', readme)
            self.assertEqual(zf.read('a.txt'), b'AAA')

    # ------------------------------------------------------------- folder group
    def test_folder_grouping(self):
        node = self._make_node()
        captured, fake_save = self._captured_save()
        load = self._payloads({
            'k1': b'X',
            'k2': b'Y',
            'k3': b'Z',
        })

        with mock.patch(f'{self.MODULE}._load_bytes', side_effect=load), \
                mock.patch(f'{self.MODULE}._save_bytes', side_effect=fake_save):
            node.execute(
                document_oss_keys=['k1', 'k2', 'k3'],
                document_names=['inv.pdf', 'recv.pdf', 'rpt.pdf'],
                item_folders=['invoices', 'invoices', 'reports'],
                archive_name='archive.zip',
            )

        with self._open_zip(captured) as zf:
            names = set(zf.namelist())
            self.assertIn('invoices/inv.pdf', names)
            self.assertIn('invoices/recv.pdf', names)
            self.assertIn('reports/rpt.pdf', names)
            self.assertIn('00_README.md', names)

    # ------------------------------------------------------------- missing file
    def test_missing_file_adds_marker(self):
        node = self._make_node()
        captured, fake_save = self._captured_save()
        load = self._payloads({
            'k1': b'AAA',
            'k2': None,  # explicitly missing
            'k3': b'CCC',
        })

        with mock.patch(f'{self.MODULE}._load_bytes', side_effect=load), \
                mock.patch(f'{self.MODULE}._save_bytes', side_effect=fake_save):
            result = node.execute(
                document_oss_keys=['k1', 'k2', 'k3'],
                document_names=['a.txt', 'b.txt', 'c.txt'],
                item_folders=[],
                archive_name='materials.zip',
            )

        self.assertEqual(result.node_variable['included_count'], 2)
        self.assertEqual(result.node_variable['missing'], ['b.txt'])
        self.assertIsNone(result.node_variable['error'])

        with self._open_zip(captured) as zf:
            names = set(zf.namelist())
            self.assertIn('a.txt', names)
            self.assertNotIn('b.txt', names)
            self.assertIn('MISSING_b.txt.txt', names)
            self.assertIn('c.txt', names)
            self.assertIn('00_README.md', names)

    # ------------------------------------------------------------- empty input
    def test_empty_input_returns_error(self):
        node = self._make_node()
        # _load_bytes / _save_bytes shouldn't even be called; patch them
        # anyway so test environment doesn't need the Django ORM.
        with mock.patch(f'{self.MODULE}._load_bytes'), \
                mock.patch(f'{self.MODULE}._save_bytes'):
            result = node.execute(
                document_oss_keys=[],
                document_names=[],
                item_folders=[],
                archive_name='materials.zip',
            )

        self.assertEqual(result.node_variable['output_oss_key'], '')
        self.assertEqual(result.node_variable['included_count'], 0)
        self.assertEqual(result.node_variable['missing'], [])
        self.assertIn('empty', (result.node_variable['error'] or '').lower())

    # ---------------------------------------------------- structural invariants
    def test_readme_always_present_and_lists_entries(self):
        node = self._make_node()
        captured, fake_save = self._captured_save()
        load = self._payloads({'k1': b'A', 'k2': None})

        with mock.patch(f'{self.MODULE}._load_bytes', side_effect=load), \
                mock.patch(f'{self.MODULE}._save_bytes', side_effect=fake_save):
            node.execute(
                document_oss_keys=['k1', 'k2'],
                # only one name provided — second falls back to 'file_1.bin'
                document_names=['a.txt'],
                item_folders=[],
                archive_name='materials.zip',
            )

        with self._open_zip(captured) as zf:
            self.assertIn('00_README.md', zf.namelist())
            readme = zf.read('00_README.md').decode('utf-8')
            self.assertIn('Included files: 1', readme)
            self.assertIn('Missing files: 1', readme)
            self.assertIn('a.txt', readme)
            self.assertIn('file_1.bin', readme)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

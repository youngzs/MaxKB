# coding=utf-8
"""
    @project: MaxKB
    @file： test_materials_sensitivity.py
    @desc: Unit tests for the SENSITIVITY GATE in `knowledge_matcher`.

    The matcher's contract: documents whose `sensitivity_level` exceeds
    the caller's clearance MUST NOT appear in the results — and the
    filter is applied at the ORM level, so an over-clearance bug in the
    application layer can't accidentally expose them.

    Because we can't boot the full Django stack on Windows dev boxes
    (one upstream app needs POSIX-only `pwd`), these tests work by
    monkey-patching `Document.objects` with a fake manager that records
    the kwargs the matcher passed in. That way we can assert the SQL
    filter went through, regardless of database availability.
"""
import sys
import types
import uuid
from unittest import TestCase, mock

from common.constants.sensitivity_constants import SensitivityLevel
from finance.service.knowledge_matcher import match_documents_for_items
from finance.service.sensitivity import is_visible, levels_up_to


class _FakeDoc:
    """Stand-in for a knowledge.Document row."""

    def __init__(self, id_, name, sensitivity_level, knowledge_id):
        self.id = id_
        self.name = name
        self.sensitivity_level = sensitivity_level
        self.knowledge_id = knowledge_id


class _FakeQuerySet:
    """Minimal QuerySet that supports `.filter().order_by()[:n]` and remembers calls."""

    def __init__(self, rows, calls):
        self._rows = list(rows)
        self._calls = calls

    def filter(self, **kwargs):
        self._calls.append(kwargs)
        rows = self._rows
        if 'sensitivity_level__in' in kwargs:
            allowed = set(kwargs['sensitivity_level__in'])
            rows = [r for r in rows if r.sensitivity_level in allowed]
        if 'knowledge_id__in' in kwargs:
            allowed = set(kwargs['knowledge_id__in'])
            rows = [r for r in rows if r.knowledge_id in allowed]
        if 'is_active' in kwargs:
            # _FakeDoc has no is_active attr; treat as truthy.
            pass
        if 'name__icontains' in kwargs:
            needle = kwargs['name__icontains'].lower()
            rows = [r for r in rows if needle in r.name.lower()]
        return _FakeQuerySet(rows, self._calls)

    def order_by(self, *_args, **_kwargs):
        return self

    def __getitem__(self, sl):
        return list(self._rows[sl] if isinstance(sl, slice) else [self._rows[sl]])

    def __iter__(self):
        return iter(self._rows)


class _FakeManager:
    def __init__(self, rows):
        self._rows = rows
        self.calls: list[dict] = []

    def filter(self, **kwargs):
        return _FakeQuerySet(self._rows, self.calls).filter(**kwargs)


class _FakeProject:
    def __init__(self, kb_ids):
        self.knowledge_base_ids = kb_ids


class _FakeProjectMgr:
    def __init__(self, project):
        self._project = project

    def filter(self, **_kwargs):
        return self

    def first(self):
        return self._project


def _install_fake_models(rows, project):
    """Build a fake `knowledge.models` + `finance.models` for the matcher."""
    fake_doc_mod = types.ModuleType('knowledge.models')
    fake_doc = type('Document', (), {'objects': _FakeManager(rows)})
    fake_doc_mod.Document = fake_doc

    fake_fin_mod = types.ModuleType('finance.models')
    fake_proj = type('FinanceProject', (), {'objects': _FakeProjectMgr(project)})
    fake_fin_mod.FinanceProject = fake_proj
    return fake_doc_mod, fake_fin_mod, fake_doc


class SensitivityHelperTest(TestCase):
    def test_levels_up_to_internal(self):
        levels = levels_up_to('internal')
        self.assertEqual(levels, ['public', 'internal'])

    def test_levels_up_to_secret(self):
        self.assertEqual(
            levels_up_to('secret'),
            ['public', 'internal', 'confidential', 'secret'],
        )

    def test_unknown_level_clamps_to_internal(self):
        # Unknown clearance must NOT silently grant secret-tier access.
        levels = levels_up_to('bogus')
        self.assertIn('public', levels)
        self.assertNotIn('secret', levels)

    def test_is_visible(self):
        self.assertTrue(is_visible('public', 'internal'))
        self.assertTrue(is_visible('internal', 'internal'))
        self.assertFalse(is_visible('confidential', 'internal'))
        self.assertFalse(is_visible('secret', 'internal'))


class MatcherSensitivityGateTest(TestCase):
    def setUp(self):
        self.kb_id = str(uuid.uuid4())
        self.rows = [
            _FakeDoc(uuid.uuid4(), '财务报表 (公开版)', SensitivityLevel.PUBLIC.value, self.kb_id),
            _FakeDoc(uuid.uuid4(), '财务报表 内部', SensitivityLevel.INTERNAL.value, self.kb_id),
            _FakeDoc(uuid.uuid4(), '财务报表 机密', SensitivityLevel.CONFIDENTIAL.value, self.kb_id),
            _FakeDoc(uuid.uuid4(), '财务报表 涉密', SensitivityLevel.SECRET.value, self.kb_id),
        ]
        self.project = _FakeProject([self.kb_id])
        self.items = [{'key': 'fin_report', 'label': '财务报表'}]

    def _run(self, user_max):
        knowledge_mod, finance_mod, _doc_cls = _install_fake_models(self.rows, self.project)
        with mock.patch.dict(
            sys.modules,
            {'knowledge.models': knowledge_mod, 'finance.models': finance_mod},
        ):
            return match_documents_for_items(
                items=self.items,
                workspace_id=uuid.uuid4(),
                project_id=uuid.uuid4(),
                user_max_sensitivity=user_max,
            )

    def test_internal_user_cannot_see_confidential_or_secret(self):
        out = self._run('internal')
        levels = {r['sensitivity_level'] for r in out}
        # SQL-level filter — confidential/secret must NOT appear.
        self.assertNotIn(SensitivityLevel.CONFIDENTIAL.value, levels)
        self.assertNotIn(SensitivityLevel.SECRET.value, levels)
        # Visible levels are present.
        self.assertIn(SensitivityLevel.PUBLIC.value, levels)
        self.assertIn(SensitivityLevel.INTERNAL.value, levels)

    def test_secret_user_sees_all(self):
        out = self._run('secret')
        levels = {r['sensitivity_level'] for r in out}
        self.assertEqual(
            levels,
            {
                SensitivityLevel.PUBLIC.value,
                SensitivityLevel.INTERNAL.value,
                SensitivityLevel.CONFIDENTIAL.value,
                SensitivityLevel.SECRET.value,
            },
        )

    def test_public_user_sees_only_public(self):
        out = self._run('public')
        levels = {r['sensitivity_level'] for r in out}
        self.assertEqual(levels, {SensitivityLevel.PUBLIC.value})

    def test_sql_filter_was_applied(self):
        """The matcher must call .filter(sensitivity_level__in=...) — not Python-side."""
        knowledge_mod, finance_mod, doc_cls = _install_fake_models(self.rows, self.project)
        with mock.patch.dict(
            sys.modules,
            {'knowledge.models': knowledge_mod, 'finance.models': finance_mod},
        ):
            match_documents_for_items(
                items=self.items,
                workspace_id=uuid.uuid4(),
                project_id=uuid.uuid4(),
                user_max_sensitivity='internal',
            )
        applied = doc_cls.objects.calls
        # First filter call should carry the sensitivity gate.
        self.assertTrue(any('sensitivity_level__in' in c for c in applied))

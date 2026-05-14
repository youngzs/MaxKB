# coding=utf-8
"""
    @project: MaxKB
    @file:   test_workflow_executor.py
    @desc:   Tests for finance.service.workflow_executor (Gate 8 Track A).

    We mock the workflow-engine internals (``WorkflowManage``, ``Workflow``,
    ``Application``) so the tests run without a DB or the full flow stack:

      - run_workflow loads the right Application by id, instantiates
        WorkflowManage with the inputs, runs it, returns the extracted output
      - WorkflowExecutionError is raised when the Application is missing,
        when WorkflowManage.run() raises, and when the run finishes with a
        non-200 status
      - the document task falls back to the direct service call when
        run_workflow raises WorkflowExecutionError
"""
import sys
import types
import uuid
from unittest import TestCase, mock

from finance.service import workflow_executor as we


# --------------------------------------------------------------------------
# helpers — a fake WorkflowManage + injectable module stand-ins
# --------------------------------------------------------------------------


class _FakeWorkflowManage:
    """Stand-in for application.flow.workflow_manage.WorkflowManage."""

    last_instance = None

    def __init__(self, flow, params, post_handler, form_data=None, **kwargs):
        self.flow = flow
        self.params = params
        self.post_handler = post_handler
        self.form_data = form_data
        self.status = 200
        self.ran = False
        self._details = {
            'node-a': {'type': 'ai-chat-node', 'answer': 'filled text'},
            'node-b': {'type': 'docx-render-node', 'output_oss_key': 'oss-123',
                       'error': None},
        }
        _FakeWorkflowManage.last_instance = self

    def run(self):
        self.ran = True
        return None

    def get_runtime_details(self):
        return self._details


def _install_fake_engine(monkeypatch_app, *, app_row, wf_manage_cls):
    """
    Patch the lazy imports inside run_workflow. run_workflow imports:
      application.flow.common.Workflow
      application.flow.i_step_node.WorkFlowPostHandler
      application.flow.workflow_manage.WorkflowManage
      application.models.application.Application
    We inject lightweight fakes into sys.modules for the duration of a test.
    """
    common_mod = types.ModuleType('application.flow.common')
    common_mod.Workflow = mock.MagicMock(name='Workflow')

    istep_mod = types.ModuleType('application.flow.i_step_node')
    istep_mod.WorkFlowPostHandler = mock.MagicMock(name='WorkFlowPostHandler')

    wfm_mod = types.ModuleType('application.flow.workflow_manage')
    wfm_mod.WorkflowManage = wf_manage_cls

    app_mod = types.ModuleType('application.models.application')
    app_mod.Application = monkeypatch_app

    return {
        'application.flow.common': common_mod,
        'application.flow.i_step_node': istep_mod,
        'application.flow.workflow_manage': wfm_mod,
        'application.models.application': app_mod,
    }


class _FakeApplicationQS:
    """Mimics Application.objects.filter(id=...).first()."""

    def __init__(self, row):
        self._row = row

    def filter(self, **kwargs):
        return self

    def first(self):
        return self._row


def _fake_application_model(row):
    m = mock.MagicMock(name='Application')
    m.objects = _FakeApplicationQS(row)
    return m


class _AppRow:
    def __init__(self, work_flow):
        self.work_flow = work_flow


# --------------------------------------------------------------------------
# run_workflow — happy path
# --------------------------------------------------------------------------


class RunWorkflowHappyPathTest(TestCase):
    def test_loads_application_passes_inputs_and_returns_output(self):
        app_row = _AppRow({'nodes': [{'id': 'start-node'}], 'edges': []})
        fake_app_model = _fake_application_model(app_row)
        modules = _install_fake_engine(
            fake_app_model, app_row=app_row, wf_manage_cls=_FakeWorkflowManage
        )
        inputs = {'template_id': 't-1', 'project_id': 'p-1',
                  'placeholder_keys': ['intro']}

        with mock.patch.dict(sys.modules, modules):
            out = we.run_workflow(
                we.DOC_GENERATOR_APP_ID, inputs, workspace_id='default'
            )

        # the fake WorkflowManage was instantiated and run
        inst = _FakeWorkflowManage.last_instance
        self.assertIsNotNone(inst)
        self.assertTrue(inst.ran)
        # inputs were threaded into params + form_data
        self.assertEqual(inst.params['application_id'], we.DOC_GENERATOR_APP_ID)
        self.assertEqual(inst.params['workspace_id'], 'default')
        self.assertEqual(inst.params['template_id'], 't-1')
        self.assertIn('template_id', inst.form_data)
        # output extracted from runtime details
        self.assertEqual(out['output_oss_key'], 'oss-123')
        self.assertEqual(out['answer'], 'filled text')
        self.assertEqual(out['_node_count'], 2)


# --------------------------------------------------------------------------
# run_workflow — failure modes
# --------------------------------------------------------------------------


class RunWorkflowFailureTest(TestCase):
    def test_missing_application_raises(self):
        fake_app_model = _fake_application_model(None)  # .first() -> None
        modules = _install_fake_engine(
            fake_app_model, app_row=None, wf_manage_cls=_FakeWorkflowManage
        )
        with mock.patch.dict(sys.modules, modules):
            with self.assertRaises(we.WorkflowExecutionError) as ctx:
                we.run_workflow(we.DOC_GENERATOR_APP_ID, {}, workspace_id='default')
        self.assertIn('not found', str(ctx.exception))

    def test_empty_workflow_nodes_raises(self):
        app_row = _AppRow({'nodes': [], 'edges': []})
        fake_app_model = _fake_application_model(app_row)
        modules = _install_fake_engine(
            fake_app_model, app_row=app_row, wf_manage_cls=_FakeWorkflowManage
        )
        with mock.patch.dict(sys.modules, modules):
            with self.assertRaises(we.WorkflowExecutionError) as ctx:
                we.run_workflow(we.DOC_GENERATOR_APP_ID, {}, workspace_id='default')
        self.assertIn('empty work_flow', str(ctx.exception))

    def test_run_raising_is_wrapped(self):
        class _BoomWFM(_FakeWorkflowManage):
            def run(self):
                raise RuntimeError('node blew up')

        app_row = _AppRow({'nodes': [{'id': 'start-node'}], 'edges': []})
        fake_app_model = _fake_application_model(app_row)
        modules = _install_fake_engine(
            fake_app_model, app_row=app_row, wf_manage_cls=_BoomWFM
        )
        with mock.patch.dict(sys.modules, modules):
            with self.assertRaises(we.WorkflowExecutionError) as ctx:
                we.run_workflow(we.DOC_GENERATOR_APP_ID, {}, workspace_id='default')
        self.assertIn('raised during run', str(ctx.exception))

    def test_non_200_status_raises(self):
        class _FailedStatusWFM(_FakeWorkflowManage):
            def run(self):
                self.ran = True
                self.status = 500
                return None

        app_row = _AppRow({'nodes': [{'id': 'start-node'}], 'edges': []})
        fake_app_model = _fake_application_model(app_row)
        modules = _install_fake_engine(
            fake_app_model, app_row=app_row, wf_manage_cls=_FailedStatusWFM
        )
        with mock.patch.dict(sys.modules, modules):
            with self.assertRaises(we.WorkflowExecutionError) as ctx:
                we.run_workflow(we.DOC_GENERATOR_APP_ID, {}, workspace_id='default')
        self.assertIn('status=500', str(ctx.exception))


# --------------------------------------------------------------------------
# feature flag + io summary
# --------------------------------------------------------------------------


class FeatureFlagTest(TestCase):
    def test_use_workflow_engine_defaults_off(self):
        with mock.patch.dict('os.environ', {}, clear=True):
            self.assertFalse(we.use_workflow_engine())

    def test_use_workflow_engine_honours_truthy_env(self):
        for raw in ('1', 'true', 'TRUE', 'yes', 'on'):
            with mock.patch.dict('os.environ', {'FINANCE_USE_WORKFLOW_ENGINE': raw}):
                self.assertTrue(we.use_workflow_engine(), raw)

    def test_use_workflow_engine_honours_falsy_env(self):
        for raw in ('0', 'false', 'no', 'off', ''):
            with mock.patch.dict('os.environ', {'FINANCE_USE_WORKFLOW_ENGINE': raw}):
                self.assertFalse(we.use_workflow_engine(), raw)


class SummarizeIoTest(TestCase):
    def test_summary_records_engine_and_redacted_keys(self):
        summary = we.summarize_io(
            engine='workflow',
            app_id=we.DOC_GENERATOR_APP_ID,
            inputs={'template_id': 'secret-t', 'placeholder_values': {'a': 'b'}},
            output={'output_oss_key': 'oss-9', '_node_count': 4},
        )
        self.assertEqual(summary['engine'], 'workflow')
        self.assertEqual(summary['app_id'], we.DOC_GENERATOR_APP_ID)
        self.assertEqual(summary['node_count'], 4)
        # only KEY NAMES, never values
        self.assertEqual(
            summary['inputs_summary'], ['placeholder_values', 'template_id']
        )
        self.assertEqual(summary['output_summary'], ['output_oss_key'])
        self.assertNotIn('secret-t', str(summary))


# --------------------------------------------------------------------------
# task-level fallback — when run_workflow raises, the direct path runs
# --------------------------------------------------------------------------


class _FakeGen:
    """Stand-in for a DocumentGeneration row used by the fallback test."""

    def __init__(self):
        self.id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.template_id = uuid.uuid4()
        self.workspace_id = 'default'
        self.placeholder_values = {'intro': 'x'}
        self.status = 'generating'
        self.error_message = ''
        self.output_oss_key = ''
        self.workflow_run_id = None
        self.created_by = uuid.uuid4()

    def save(self, update_fields=None):
        return None

    def refresh_from_db(self):
        return None


class DocumentTaskFallbackTest(TestCase):
    """
    The document task's ``_try_workflow_engine`` helper must return None
    (→ caller falls back to direct service) when run_workflow raises
    WorkflowExecutionError, and also when the engine flag is off.
    """

    def test_returns_none_when_flag_off(self):
        from finance.tasks.documents import _try_workflow_engine

        with mock.patch.object(we, 'use_workflow_engine', return_value=False):
            result = _try_workflow_engine(_FakeGen())
        self.assertIsNone(result)

    def test_returns_none_when_run_workflow_raises(self):
        from finance.tasks.documents import _try_workflow_engine

        with mock.patch.object(we, 'use_workflow_engine', return_value=True), \
                mock.patch.object(
                    we, 'run_workflow',
                    side_effect=we.WorkflowExecutionError('preset incomplete'),
                ):
            result = _try_workflow_engine(_FakeGen())
        # None → the task falls through to trigger_generation (direct path)
        self.assertIsNone(result)

    def test_returns_none_when_run_workflow_raises_unexpected(self):
        from finance.tasks.documents import _try_workflow_engine

        with mock.patch.object(we, 'use_workflow_engine', return_value=True), \
                mock.patch.object(
                    we, 'run_workflow', side_effect=RuntimeError('boom'),
                ):
            result = _try_workflow_engine(_FakeGen())
        self.assertIsNone(result)

    def test_returns_output_on_engine_success(self):
        from finance.tasks.documents import _try_workflow_engine

        with mock.patch.object(we, 'use_workflow_engine', return_value=True), \
                mock.patch.object(
                    we, 'run_workflow',
                    return_value={'output_oss_key': 'oss-77', 'error': None,
                                  '_node_count': 3},
                ):
            result = _try_workflow_engine(_FakeGen())
        self.assertIsNotNone(result)
        self.assertEqual(result['output']['output_oss_key'], 'oss-77')
        self.assertEqual(result['summary']['engine'], 'workflow')
        self.assertEqual(result['summary']['node_count'], 3)

# coding=utf-8
"""
    @project: MaxKB
    @file:   test_perf.py
    @desc:   Tests for the slow-op instrumentation decorator
    (Gate 6 Track C / C4).

    Validates:
      * fast calls do NOT log
      * slow calls log WARN with the expected label + duration shape
      * exceptions still trigger the log (finally block)
      * workspace_id resolution from kwargs and positional args
"""
from __future__ import annotations

import time
from unittest.mock import patch

from django.test import SimpleTestCase

from finance.service.perf import _resolve_workspace, log_slow


class LogSlowDecoratorTest(SimpleTestCase):
    def test_fast_call_does_not_log(self):
        @log_slow(threshold_ms=500)
        def quick():
            return 'ok'

        with patch('finance.service.perf.maxkb_logger') as mock_logger:
            result = quick()
            self.assertEqual(result, 'ok')
            mock_logger.warning.assert_not_called()

    def test_slow_call_logs_warning(self):
        @log_slow(threshold_ms=10, name='slow.fn')
        def slow():
            time.sleep(0.05)  # 50ms — well over 10ms threshold
            return 'done'

        with patch('finance.service.perf.maxkb_logger') as mock_logger:
            result = slow()
            self.assertEqual(result, 'done')
            mock_logger.warning.assert_called_once()
            msg = mock_logger.warning.call_args[0][0]
            self.assertIn('slow.fn', msg)
            self.assertIn('[perf]', msg)
            self.assertIn('workspace=', msg)

    def test_logs_on_exception_too(self):
        @log_slow(threshold_ms=10, name='boom')
        def boom():
            time.sleep(0.05)
            raise RuntimeError('nope')

        with patch('finance.service.perf.maxkb_logger') as mock_logger:
            with self.assertRaises(RuntimeError):
                boom()
            mock_logger.warning.assert_called_once()
            msg = mock_logger.warning.call_args[0][0]
            self.assertIn('boom', msg)

    def test_workspace_id_from_kwargs(self):
        @log_slow(threshold_ms=10, name='ws.kw')
        def call(workspace_id):
            time.sleep(0.03)

        with patch('finance.service.perf.maxkb_logger') as mock_logger:
            call(workspace_id='workspace-42')
            msg = mock_logger.warning.call_args[0][0]
            self.assertIn('workspace=workspace-42', msg)

    def test_default_label_uses_qualname(self):
        @log_slow(threshold_ms=10)
        def labelled_fn():
            time.sleep(0.03)

        with patch('finance.service.perf.maxkb_logger') as mock_logger:
            labelled_fn()
            msg = mock_logger.warning.call_args[0][0]
            self.assertIn('labelled_fn', msg)


class ResolveWorkspaceTest(SimpleTestCase):
    def test_prefers_kwarg(self):
        self.assertEqual(
            _resolve_workspace(('self', 'pos-ws'), {'workspace_id': 'kw-ws'}),
            'kw-ws',
        )

    def test_falls_back_to_second_positional(self):
        self.assertEqual(_resolve_workspace(('self', 'pos-ws'), {}), 'pos-ws')

    def test_falls_back_to_first_positional_string(self):
        self.assertEqual(_resolve_workspace(('ws-only',), {}), 'ws-only')

    def test_placeholder_when_no_match(self):
        self.assertEqual(_resolve_workspace((), {}), '?')
        self.assertEqual(_resolve_workspace((123,), {}), '?')

# coding=utf-8
"""
    @project: MaxKB
    @file:   workflow_executor.py
    @desc:   Bridges finance Celery tasks to MaxKB's workflow engine.

    Loads a preset workflow Application by its deterministic id, injects
    inputs, runs it synchronously (we are already inside a Celery worker
    thread), and extracts the structured output.

    -------------------------------------------------------------------------
    STATUS — flag-OFF by default. Read this before flipping it on.
    -------------------------------------------------------------------------
    Phase 1 exploration found that MaxKB's ``WorkflowManage`` cannot run the
    finance preset workflows cleanly from a Celery worker *as the presets are
    currently authored*:

      1. ``WorkflowManage`` hard-requires a ``WorkFlowPostHandler`` whose
         ``.handler()`` dereferences a ``ChatInfo`` object — it calls
         ``chat_info.append_chat_record()`` / ``set_cache()`` and fires
         ``extract_long_term_memory.apply_async``. ``run_block`` invokes the
         post-handler unconditionally.
      2. ``BaseStartStepNode.execute()`` calls
         ``workflow_manage.get_chat_info().get_chat_variable()`` — without a
         real ``ChatInfo`` the start node raises immediately.
      3. The preset JSON node_data for ``docx-render-node`` / ``zip-pack-node``
         uses ``*_reference`` arrays (``template_oss_key_reference``,
         ``placeholder_values_reference``, ...). But ``IDocxRenderNode._run``
         reads ``node_params_serializer.data`` directly and the serializer
         *requires* a literal ``template_oss_key`` (non-blank) +
         ``placeholder_values`` dict. There is no reference-resolution wiring
         for these two node types — the JSON ``_install_note`` fields say so
         explicitly ("此节点作为骨架占位以保证图完整" — skeleton placeholder
         to keep the graph complete).

    So the preset workflows are structurally incomplete: the docx/zip nodes'
    input contract was never implemented. Wiring this reliably would mean
    rewriting the preset JSONs AND adding reference-resolution to the docx/zip
    nodes — out of scope for a "last mile" wiring task and risky to the
    currently-working async pipeline.

    Therefore: ``FINANCE_USE_WORKFLOW_ENGINE`` defaults to **False**. The
    direct-service-call path in the Celery tasks stays primary. This module
    provides ``run_workflow`` as a best-effort bridge with a synthetic
    chat-info shim so the path *can* be exercised (e.g. once the presets are
    fixed) by setting ``FINANCE_USE_WORKFLOW_ENGINE=true``, and so the task
    fallback logic is testable. It is not relied upon in production yet.
"""
from __future__ import annotations

import os
import uuid as _uuid
from typing import Optional

from common.utils.logger import maxkb_logger


# Deterministic IDs from install_finance_workflows (UUID-5 derived from slug).
DOC_GENERATOR_APP_ID = '456c2b79-1b43-565c-9058-e87b0b546114'
MATERIALS_PACKAGER_APP_ID = '804a685a-ac63-5f04-8cce-1e44a69a770f'


def _env_flag(name: str, default: bool) -> bool:
    """Read a boolean env var. Accepts 1/true/yes/on (case-insensitive)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


# Default OFF — see the module docstring for the precise reasoning. The flag
# is read at call time (not import time) so tests can monkey-patch
# ``os.environ`` without reloading the module.
def use_workflow_engine() -> bool:
    """Return whether tasks should attempt the workflow-engine path."""
    return _env_flag('FINANCE_USE_WORKFLOW_ENGINE', False)


class WorkflowExecutionError(Exception):
    """
    Raised by ``run_workflow`` on any failure to load / instantiate / run a
    preset workflow. Celery tasks catch this and fall back to the direct
    service call — it is never fatal to the pipeline.
    """


# --------------------------------------------------------------------------
# Synthetic chat-info shim
# --------------------------------------------------------------------------
#
# ``WorkflowManage`` + ``BaseStartStepNode`` reach into a ``ChatInfo`` object
# via the ``WorkFlowPostHandler``. We are not in a chat session, so we feed a
# minimal duck-typed stand-in that satisfies every attribute/method the
# block-execution path touches without persisting anything.


class _ShimChatInfo:
    """Minimal ChatInfo stand-in for headless (non-chat) workflow runs."""

    def __init__(self, application_id: str, workspace_id: str):
        self.application_id = application_id
        self.workspace_id = workspace_id
        self.ip_address = ''
        self.source = 'FINANCE_INTERNAL'
        self.debug = False
        self.chat_record_list = []

    def append_chat_record(self, chat_record):  # noqa: D401 - shim
        # Headless run: we deliberately do not persist a ChatRecord.
        return None

    def set_cache(self):  # noqa: D401 - shim
        return None

    def get_chat_variable(self):  # noqa: D401 - shim
        return {}

    def get_chat_user(self):  # noqa: D401 - shim
        return None

    def get_chat_user_group(self):  # noqa: D401 - shim
        return None


def _build_params(app_id: str, inputs: dict, workspace_id: str) -> dict:
    """
    Assemble the ``params`` dict ``WorkflowManage`` / ``FlowParamsSerializer``
    expect. ``inputs`` keys are merged in as ``form_data``-style globals so
    start-node references resolve. ``stream`` is False so ``run_block`` is
    used (synchronous, returns once the graph is done).
    """
    return {
        'history_chat_record': [],
        'question': inputs.get('question', ''),
        'chat_id': str(_uuid.uuid4()),
        'chat_record_id': str(_uuid.uuid4()),
        'stream': False,
        're_chat': False,
        'debug': False,
        'workspace_id': str(workspace_id),
        'application_id': str(app_id),
        # finance inputs surface as workflow globals / form_data
        **{k: v for k, v in (inputs or {}).items() if k != 'question'},
    }


def _extract_output(work_flow_manage) -> dict:
    """
    Pull the structured output out of a finished ``WorkflowManage``. The
    ``end-node`` does not itself hold output; the result-producing node
    (docx-render / zip-pack, ``is_result: true``) writes ``output_oss_key``
    etc. into its ``context``. We walk the runtime details and return the
    last result node's context-ish fields plus the assembled answer text.
    """
    details = {}
    try:
        details = work_flow_manage.get_runtime_details() or {}
    except Exception as e:  # noqa: BLE001
        maxkb_logger.warning(
            f'[finance.workflow_executor] could not read runtime details: {e}'
        )

    result_keys = (
        'output_oss_key', 'error', 'included_count', 'missing', 'answer',
    )
    output: dict = {}
    node_count = 0
    for node_detail in details.values():
        node_count += 1
        for key in result_keys:
            if key in node_detail and node_detail.get(key) not in (None, ''):
                output[key] = node_detail.get(key)
    output['_node_count'] = node_count
    return output


def run_workflow(app_id: str, inputs: dict, workspace_id: str) -> dict:
    """
    Load the Application's ``work_flow`` JSON, instantiate ``WorkflowManage``,
    run it with ``inputs``, and return the final output dict.

    ``inputs`` keys map to the workflow's start-node fields (e.g.
    ``template_id`` / ``project_id`` / ``placeholder_keys`` for the document
    generator). The exact contract is defined by the preset JSONs under
    ``apps/finance/data/internal_workflows/``.

    Raises ``WorkflowExecutionError`` on any failure — the caller (Celery
    task) is expected to catch it and fall back to the direct service call.

    NOTE: as documented at module scope, the preset workflows' docx/zip nodes
    have an unimplemented ``*_reference`` input contract, so this will
    typically raise for the real presets. It is kept correct + testable so
    the path can be flipped on once the presets are completed.
    """
    inputs = inputs or {}
    try:
        from application.flow.common import Workflow
        from application.flow.i_step_node import WorkFlowPostHandler
        from application.flow.workflow_manage import WorkflowManage
        from application.models.application import Application
    except Exception as e:  # noqa: BLE001 - import guard
        raise WorkflowExecutionError(
            f'workflow engine modules unavailable: {e!r}'
        ) from e

    application = Application.objects.filter(id=app_id).first()
    if application is None:
        raise WorkflowExecutionError(
            f'preset workflow Application {app_id} not found — '
            'run `install_finance_workflows` first'
        )

    work_flow = application.work_flow or {}
    if not work_flow.get('nodes'):
        raise WorkflowExecutionError(
            f'preset workflow Application {app_id} has empty work_flow.nodes'
        )

    params = _build_params(app_id, inputs, workspace_id)
    chat_info = _ShimChatInfo(str(app_id), str(workspace_id))

    try:
        work_flow_manage = WorkflowManage(
            Workflow.new_instance(work_flow),
            params,
            WorkFlowPostHandler(chat_info),
            form_data={k: v for k, v in inputs.items() if k != 'question'},
        )
    except Exception as e:  # noqa: BLE001
        raise WorkflowExecutionError(
            f'failed to instantiate WorkflowManage for {app_id}: {e!r}'
        ) from e

    try:
        work_flow_manage.run()
    except Exception as e:  # noqa: BLE001
        raise WorkflowExecutionError(
            f'workflow {app_id} raised during run: {e!r}'
        ) from e

    # ``run_block`` sets ``status`` to 500 on any node failure instead of
    # raising. Surface that as an execution error so the caller falls back.
    status = getattr(work_flow_manage, 'status', 200)
    output = _extract_output(work_flow_manage)
    if status != 200:
        raise WorkflowExecutionError(
            f'workflow {app_id} finished with status={status}; '
            f'output={output}'
        )
    return output


def summarize_io(
    *, engine: str, app_id: Optional[str], inputs: dict, output: dict,
) -> dict:
    """
    Build the redacted ``WorkflowRun.payload`` enrichment block so the audit
    trail can distinguish workflow-engine runs from direct-call runs.

    We record only *key names* for inputs/outputs (never values) — finance
    inputs can carry sensitive project context.
    """
    inputs = inputs or {}
    output = output or {}
    node_count = output.get('_node_count')
    return {
        'engine': engine,
        'app_id': str(app_id) if app_id else None,
        'node_count': node_count,
        'inputs_summary': sorted(str(k) for k in inputs.keys()),
        'output_summary': sorted(
            str(k) for k in output.keys() if k != '_node_count'
        ),
    }

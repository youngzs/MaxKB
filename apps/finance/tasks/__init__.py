# coding=utf-8
"""
    @project: MaxKB
    @file:   __init__.py
    @desc:   Finance Celery tasks (Gate 7 Track B).

    Background tasks that wrap the existing service functions so HTTP
    requests can return immediately instead of waiting for an LLM round
    trip. See ``workflow_runtime`` for the shared lifecycle helpers and
    transient/business error classification.

    Public entry points:
      finance.tasks.async_parse(materials_task_id, run_id=None)
      finance.tasks.async_match(materials_task_id, run_id=None)
      finance.tasks.async_pack(materials_task_id, item_groups=None, run_id=None)
      finance.tasks.async_generate(generation_id, run_id=None)

    All four are auto-discovered by Celery via ``app.autodiscover_tasks``
    (see apps/ops/celery/__init__.py) — they only need to exist under a
    module named ``tasks`` inside an INSTALLED_APP.
"""
from .documents import async_generate
from .materials import async_match, async_pack, async_parse

__all__ = ['async_parse', 'async_match', 'async_pack', 'async_generate']

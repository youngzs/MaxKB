# coding=utf-8
"""
    @project: MaxKB
    @file： perf.py
    @desc: Slow-operation instrumentation for the finance module
    (Gate 6 Track C / C4).

    Lightweight decorator — wrap an expensive function with
    ``@log_slow(threshold_ms=1000)`` and any invocation that exceeds the
    threshold emits a single WARN line via the project logger. Designed
    for service-layer functions that aren't already captured by DRF's
    middleware-level request timing.

    Cheap fast-path: when the call comes in under threshold, the only
    overhead is two ``time.monotonic()`` reads and a comparison — well
    under 1µs on Python 3.11.
"""
from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

from common.utils.logger import maxkb_logger


def _resolve_workspace(args: tuple, kwargs: dict) -> str:
    """
    Best-effort: find a workspace id in the call's args/kwargs so the
    slow-op log line is filterable per tenant.

    Priority:
      1. explicit ``workspace_id=`` kwarg
      2. second positional arg if it looks like a workspace id string
      3. ``'?'`` placeholder otherwise
    """
    ws = kwargs.get('workspace_id')
    if ws:
        return str(ws)
    # Heuristic: most finance service methods take (self/cls, workspace_id, ...)
    # OR (workspace_id, ...) — try arg[1] first, then arg[0].
    if len(args) >= 2 and isinstance(args[1], str):
        return args[1]
    if len(args) >= 1 and isinstance(args[0], str):
        return args[0]
    return '?'


def log_slow(
    threshold_ms: int = 500,
    name: str = '',
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that logs WARN when the wrapped function takes longer
    than ``threshold_ms``.

    Args:
        threshold_ms: emit a log only when the wrapped call exceeded
            this duration. Use a generous value (≥500ms) — finance
            workflows have plenty of legitimate sub-second ops we
            don't want polluting logs.
        name: override label in the log line. Defaults to the wrapped
            function's qualified name, which is usually right.

    The wrapper logs even on exception — the duration is interesting
    regardless of whether the call succeeded, and finally-block
    semantics give us that for free.
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        label = name or getattr(fn, '__qualname__', getattr(fn, '__name__', 'fn'))

        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                return fn(*args, **kwargs)
            finally:
                dur_ms = (time.monotonic() - t0) * 1000.0
                if dur_ms >= threshold_ms:
                    ws = _resolve_workspace(args, kwargs)
                    maxkb_logger.warning(
                        f'[perf] {label} took {dur_ms:.0f}ms (workspace={ws})'
                    )

        return wrapper

    return deco

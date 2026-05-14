# coding=utf-8
"""
    @project: MaxKB
    @file： llm.py
    @desc: Single-turn LLM helpers for finance services.

    Wraps MaxKB's `models_provider` so callers do not need to know about
    credentials, model selection, or fallback behavior. The contract is:

        text = chat_completion(workspace_id, system, user)
        if text is None:  # model unavailable / call failed → fall back to heuristic
            ...

    Functions in this module MUST NOT raise — finance services rely on a
    None sentinel to switch to deterministic fallbacks so the user never
    sees a 500 from these endpoints.
"""
from __future__ import annotations

from typing import Optional

from django.db.models import QuerySet

from common.utils.logger import maxkb_logger


def get_workspace_chat_model(workspace_id: str):
    """
    Resolve the workspace's default chat model and return a langchain-compatible
    chat model instance, or None if no usable LLM is configured / instantiation
    fails. Never raises.

    Resolution order:
      1. First `model_type == 'LLM'` Model row scoped to this workspace_id
         (Model rows are scoped by workspace_id == 'default' for the global
         workspace; see models_provider.models.Model).
      2. If none in the workspace, fall back to the first global ('default')
         LLM model.
      3. None.
    """
    try:
        # Local import keeps this module importable in tests where the Django
        # app registry may not yet be ready.
        from models_provider.models import Model
        from models_provider.tools import get_model_instance_by_model_workspace_id

        model_row = QuerySet(Model).filter(
            workspace_id=workspace_id, model_type='LLM', status='SUCCESS',
        ).order_by('create_time').first()
        if model_row is None and workspace_id != 'default':
            model_row = QuerySet(Model).filter(
                workspace_id='default', model_type='LLM', status='SUCCESS',
            ).order_by('create_time').first()
        if model_row is None:
            return None
        return get_model_instance_by_model_workspace_id(model_row.id, workspace_id)
    except Exception as e:  # noqa: BLE001 — helper must never raise
        maxkb_logger.warning(f'[finance.llm] get_workspace_chat_model failed: {e}')
        return None


def chat_completion(
    workspace_id: str,
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> Optional[str]:
    """
    Single-turn chat completion against the workspace's default LLM.

    Returns the model's response text, or None if the model is unavailable or
    the call fails. Callers MUST handle None by falling back to a heuristic.

    Low temperature (0.2 default) is appropriate for structured tasks like
    JSON extraction. `max_tokens` is advisory — passed to the model if it
    accepts the kwarg, otherwise ignored.
    """
    _ = max_tokens, temperature  # reserved — model params are bound at instantiation
    model = get_workspace_chat_model(workspace_id)
    if model is None:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        resp = model.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        if resp is None:
            return None
        content = getattr(resp, 'content', None)
        if content is None:
            return str(resp)
        # Some chat models return a list-of-dicts content (multimodal). Flatten
        # to plain text for our use cases.
        if isinstance(content, list):
            parts = []
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get('type') == 'text':
                    parts.append(chunk.get('text', ''))
                elif isinstance(chunk, str):
                    parts.append(chunk)
            return ''.join(parts) or None
        return str(content)
    except Exception:
        maxkb_logger.exception('[finance.llm] chat_completion failed')
        return None

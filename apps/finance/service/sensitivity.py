# coding=utf-8
"""
    @project: MaxKB
    @file： sensitivity.py
    @desc: Helpers for SENSITIVITY GATE — deciding which documents a given
    user is allowed to see when matching knowledge against a materials task.

    Ordering (ascending): public < internal < confidential < secret.
    A user whose max is 'internal' may see public+internal documents but
    NOT confidential or secret.

    Gate 4 heuristic mapping (role → max sensitivity):
        WORKSPACE_MANAGE / ADMIN  → 'secret'    (sees everything)
        USER                       → 'internal'  (sees public + internal)

    TODO(Gate 5+): plug in per-user explicit clearance from a dedicated
    UserSensitivityClearance table, falling back to this role heuristic.
"""
from __future__ import annotations

from typing import Iterable

from common.constants.sensitivity_constants import SensitivityLevel


# Ascending order of sensitivity. Index = clearance level.
_SENSITIVITY_ORDER: list[str] = [
    SensitivityLevel.PUBLIC.value,
    SensitivityLevel.INTERNAL.value,
    SensitivityLevel.CONFIDENTIAL.value,
    SensitivityLevel.SECRET.value,
]


def _index_of(level: str) -> int:
    """Return the ascending-order index of `level`, or 1 (internal) if unknown."""
    try:
        return _SENSITIVITY_ORDER.index(level)
    except ValueError:
        # Unknown level → treat as 'internal' to fail-safe (don't accidentally
        # grant secret-tier exposure to a misconfigured document).
        return _SENSITIVITY_ORDER.index(SensitivityLevel.INTERNAL.value)


def levels_up_to(max_level: str) -> list[str]:
    """
    Return every sensitivity level the holder of `max_level` clearance can read.

    Used at SQL-filter time:
        Document.objects.filter(sensitivity_level__in=levels_up_to(user_max))
    """
    idx = _index_of(max_level)
    return _SENSITIVITY_ORDER[: idx + 1]


def is_visible(document_level: str, max_level: str) -> bool:
    """In-Python convenience check (e.g. for asserts/tests)."""
    return _index_of(document_level) <= _index_of(max_level)


def get_user_max_sensitivity(user, workspace_id) -> str:
    """
    Derive a user's max-sensitivity clearance for a workspace.

    Gate 4 implementation: role-based heuristic.
    Looks at the user's roles for the given workspace via the existing
    UserRoleRelation/Role tables; if a workspace manager / admin role is
    present, returns 'secret'; otherwise 'internal'.

    On any lookup failure we conservatively fall back to 'internal' so
    that a broken role layer can't accidentally up-grade exposure.

    TODO(Gate 5+): replace with an explicit per-user clearance lookup.
    """
    # Local imports keep this module importable in standalone contexts (tests).
    try:
        from users.models.user import UserRoleRelation
    except Exception:  # noqa: BLE001 — fail-safe to internal
        return SensitivityLevel.INTERNAL.value

    user_id = getattr(user, 'id', None)
    if user_id is None:
        return SensitivityLevel.INTERNAL.value

    try:
        ws_resource = f'/WORKSPACE/{workspace_id}'
        relations = UserRoleRelation.objects.filter(user_id=user_id)
        # We accept either an exact resource match for this workspace OR a
        # global system-level role (e.g. ADMIN with no workspace scoping).
        role_names = _collect_role_names(relations, ws_resource)
    except Exception:  # noqa: BLE001
        return SensitivityLevel.INTERNAL.value

    if any(r in ('ADMIN', 'WORKSPACE_MANAGE') for r in role_names):
        return SensitivityLevel.SECRET.value
    return SensitivityLevel.INTERNAL.value


def _collect_role_names(relations: Iterable, ws_resource: str) -> set[str]:
    """
    Extract role names from a UserRoleRelation queryset. Tolerates a couple
    of common schema layouts (role_id on the relation vs. a related Role
    object with a `name` field) so this helper survives schema drift.
    """
    names: set[str] = set()
    for rel in relations:
        # Resource scoping: accept either a matching workspace path OR an
        # unscoped/empty resource_path (system-wide role).
        resource_path = getattr(rel, 'resource_path', '') or ''
        if resource_path and resource_path != ws_resource and not resource_path.startswith('/SYSTEM'):
            continue
        # Try common field names without coupling to a specific schema.
        for attr in ('role_id', 'role'):
            val = getattr(rel, attr, None)
            if val is None:
                continue
            # If `val` is a related model with a name attribute, use it.
            name = getattr(val, 'name', None)
            if name:
                names.add(str(name))
            else:
                names.add(str(val))
    return names

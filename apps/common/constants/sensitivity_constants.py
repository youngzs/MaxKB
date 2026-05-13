# coding=utf-8
"""
    @project: maxkb
    @file:    sensitivity_constants.py
    @desc:    Document / artifact sensitivity classification.

    Shared across apps (knowledge, finance, materials packaging) so that
    downstream gates can hard-control external sharing eligibility based
    on a single, typed source of truth.
"""
from django.db import models


class SensitivityLevel(models.TextChoices):
    """
    Sensitivity classification for documents and artifacts.

    The ordering (public < internal < confidential < secret) is implicit
    and may be referenced by future filtering logic; for now only the
    raw value is stored on the model.
    """
    PUBLIC = 'public', '公开'
    INTERNAL = 'internal', '内部'
    CONFIDENTIAL = 'confidential', '机密'
    SECRET = 'secret', '涉密'

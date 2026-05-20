# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance constants package — P2「进度归集」阶段模板等纯数据常量。

    本包内的模块**不依赖** finance.models，因此可被数据迁移安全导入
    （RunPython 回填逻辑会用到 stage_templates 里的纯函数）。
"""
from .stage_templates import (
    STAGE_TEMPLATES,
    StageDef,
    build_initial_stage_plan,
    get_stage,
    get_template,
    resolve_current_stage_key,
)

__all__ = [
    'STAGE_TEMPLATES',
    'StageDef',
    'build_initial_stage_plan',
    'get_stage',
    'get_template',
    'resolve_current_stage_key',
]

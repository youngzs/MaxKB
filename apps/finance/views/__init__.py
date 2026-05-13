# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance views package
"""
from .ping import FinancePingView
from .project import FinanceProjectDetailView, FinanceProjectListView

__all__ = [
    'FinancePingView',
    'FinanceProjectListView',
    'FinanceProjectDetailView',
]

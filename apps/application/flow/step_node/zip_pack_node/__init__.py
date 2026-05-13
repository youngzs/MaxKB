# coding=utf-8
"""
    @project: maxkb
    @file:    __init__.py
    @desc:    zip_pack_node — bundles multiple OSS-stored documents into a
              single zip archive and persists the result back to the File
              blob store. See ``i_zip_pack_node.py`` for the input/output
              contract.
"""
from .impl import *  # noqa: F401,F403

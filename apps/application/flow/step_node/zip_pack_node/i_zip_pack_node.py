# coding=utf-8
"""
    @project: maxkb
    @file:    i_zip_pack_node.py
    @desc:    Interface for the ZIP-pack workflow node.

    Inputs (declared via the serializer):
        - document_oss_keys  (list[str], required)   OSS keys (== File.id) of source docs
        - document_names     (list[str], optional)   Display names; defaults to
                                                     'file_<idx>.bin' if missing
        - item_folders       (list[str], optional)   Folder names per document;
                                                     flat layout if missing
        - archive_name       (str, optional)         Defaults to 'materials.zip'

    Outputs (written to ``self.context`` by the implementation):
        - output_oss_key  (str)         OSS key of the produced zip; '' on failure
        - included_count  (int)         Number of files actually packed
        - missing         (list[str])   Names of files that couldn't be retrieved
        - error           (str | None)  Error message on catastrophic failure
"""
from typing import Type

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from application.flow.common import WorkflowMode
from application.flow.i_step_node import INode, NodeResult


class ZipPackNodeSerializer(serializers.Serializer):
    document_oss_keys = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=True,
        allow_empty=False,
        label=_('Document OSS keys'),
    )
    document_names = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=list,
        label=_('Document names'),
    )
    item_folders = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=list,
        label=_('Item folders'),
    )
    archive_name = serializers.CharField(
        required=False, allow_blank=True, default='materials.zip',
        label=_('Archive name'),
    )


class IZipPackNode(INode):
    """
    Base interface — backend type string ``zip-pack-node`` must match the
    ``type`` field on the matching frontend node directory.
    """

    type = 'zip-pack-node'
    support = [
        WorkflowMode.APPLICATION,
        WorkflowMode.APPLICATION_LOOP,
        WorkflowMode.TOOL,
        WorkflowMode.TOOL_LOOP,
    ]

    def get_node_params_serializer_class(self) -> Type[serializers.Serializer]:
        return ZipPackNodeSerializer

    def _run(self):
        data = self.node_params_serializer.data
        return self.execute(
            document_oss_keys=data.get('document_oss_keys') or [],
            document_names=data.get('document_names') or [],
            item_folders=data.get('item_folders') or [],
            archive_name=data.get('archive_name') or 'materials.zip',
        )

    def execute(self, document_oss_keys, document_names, item_folders, archive_name, **kwargs) -> NodeResult:
        pass

# coding=utf-8
"""
    @project: maxkb
    @file:    i_docx_render_node.py
    @desc:    Interface for the DOCX-render workflow node.

    Inputs (declared via the serializer):
        - template_oss_key    (str, required)   OSS key (== File.id) of the source .docx
        - placeholder_values  (dict, required)  Map of placeholder name -> value
        - output_filename     (str, optional)   Defaults to 'output.docx'

    Outputs (written to ``self.context`` by the implementation):
        - output_oss_key  (str)         OSS key of the rendered docx; '' on failure
        - error           (str | None)  Error message on failure, else None
"""
from typing import Type

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from application.flow.common import WorkflowMode
from application.flow.i_step_node import INode, NodeResult


class DocxRenderNodeSerializer(serializers.Serializer):
    template_oss_key = serializers.CharField(
        required=True, allow_blank=False, label=_('Template OSS key')
    )
    placeholder_values = serializers.DictField(
        required=True, label=_('Placeholder values')
    )
    output_filename = serializers.CharField(
        required=False, allow_blank=True, default='output.docx',
        label=_('Output filename')
    )


class IDocxRenderNode(INode):
    """
    Base interface — backend type string ``docx-render-node`` must match the
    ``type`` field on the matching frontend node directory.
    """

    type = 'docx-render-node'
    support = [
        WorkflowMode.APPLICATION,
        WorkflowMode.APPLICATION_LOOP,
        WorkflowMode.TOOL,
        WorkflowMode.TOOL_LOOP,
    ]

    def get_node_params_serializer_class(self) -> Type[serializers.Serializer]:
        return DocxRenderNodeSerializer

    def _run(self):
        data = self.node_params_serializer.data
        return self.execute(
            template_oss_key=data.get('template_oss_key'),
            placeholder_values=data.get('placeholder_values') or {},
            output_filename=data.get('output_filename') or 'output.docx',
        )

    def execute(self, template_oss_key, placeholder_values, output_filename, **kwargs) -> NodeResult:
        pass

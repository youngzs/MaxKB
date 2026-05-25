# coding=utf-8
"""
    @project: maxkb
    @file: ocr_setting.py
    @desc: OCR 系统设置（视觉大模型 / 本地 OCR 二选一）。
"""
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from common.exception.app_exception import AppApiException
from common.handle.impl.ocr.provider import (
    ALL_MODES,
    MODE_TEXTIN,
    MODE_VISION_LLM,
    OcrConfigError,
    OcrError,
    get_ocr_provider,
)
from common.utils.logger import maxkb_logger
from system_manage.models import SettingType, SystemSetting

# 默认配置：未保存过时 GET 返回这个，前端用它做表单初值
DEFAULTS = {
    'mode': MODE_VISION_LLM,
    'model_id': '',
    'workspace_id': '',
    'language': 'ch',  # 仅 local 模式有意义
    'prompt': '',      # 空时 provider 用 DEFAULT_OCR_PROMPT
    # TextIn 模式参数。凭据只落库不进代码。
    'textin_app_id': '',
    'textin_secret_code': '',
    'textin_endpoint': '',  # 留空走 provider 默认 https://api.textin.com/api/v1/xparse/parse/sync
}


class OcrSettingSerializer(serializers.Serializer):
    """读 / 写口子，风格对齐 EmailSettingSerializer。"""

    @staticmethod
    def one():
        record = QuerySet(SystemSetting).filter(type=SettingType.OCR.value).first()
        merged = dict(DEFAULTS)
        if record is not None and isinstance(record.meta, dict):
            for k, v in record.meta.items():
                merged[k] = v
        return merged

    class Create(serializers.Serializer):
        mode = serializers.ChoiceField(choices=ALL_MODES, required=True, label=_('OCR Mode'))
        # 视觉大模型模式必填
        model_id = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                         max_length=64, label=_('Vision Model'))
        workspace_id = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                             max_length=64, label=_('Workspace'))
        # 本地 OCR 模式参数
        language = serializers.CharField(required=False, allow_blank=True, max_length=16,
                                         label=_('OCR Language'))
        # 可选自定义 prompt（视觉模型模式生效）
        prompt = serializers.CharField(required=False, allow_blank=True, max_length=2048,
                                       label=_('OCR Prompt'))
        # TextIn 模式参数（凭据落库存储）
        textin_app_id = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                              max_length=128, label=_('TextIn App ID'))
        textin_secret_code = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                                   max_length=256, label=_('TextIn Secret Code'))
        textin_endpoint = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                                max_length=512, label=_('TextIn Endpoint'))

        def validate(self, attrs):
            if attrs.get('mode') == MODE_VISION_LLM and not attrs.get('model_id'):
                raise serializers.ValidationError(
                    {'model_id': _('Vision model is required when mode is vision_model')})
            if attrs.get('mode') == MODE_TEXTIN:
                if not attrs.get('textin_app_id'):
                    raise serializers.ValidationError(
                        {'textin_app_id': _('TextIn app_id is required when mode is textin')})
                if not attrs.get('textin_secret_code'):
                    raise serializers.ValidationError(
                        {'textin_secret_code': _('TextIn secret_code is required when mode is textin')})
            return attrs

        def is_valid_config(self):
            """主动跑一次 provider 初始化，验证 model_id 可加载 / rapidocr 已安装等。
            纯校验用，不实际识别图片。"""
            super().is_valid(raise_exception=True)
            try:
                get_ocr_provider(self.to_meta())
            except OcrConfigError as e:
                raise AppApiException(1004, str(e))
            except OcrError as e:
                raise AppApiException(1004, str(e))
            except Exception as e:
                maxkb_logger.error(f'OCR config validation failed: {e}')
                raise AppApiException(1004, _('OCR configuration test failed: {error}').format(error=str(e)))
            return True

        def update_or_save(self):
            super().is_valid(raise_exception=True)
            record = QuerySet(SystemSetting).filter(type=SettingType.OCR.value).first()
            if record is None:
                record = SystemSetting(type=SettingType.OCR.value)
            record.meta = self.to_meta()
            record.save()
            return record.meta

        def to_meta(self):
            d = self.validated_data
            return {
                'mode': d.get('mode'),
                'model_id': d.get('model_id') or '',
                'workspace_id': d.get('workspace_id') or '',
                'language': d.get('language') or 'ch',
                'prompt': d.get('prompt') or '',
                'textin_app_id': d.get('textin_app_id') or '',
                'textin_secret_code': d.get('textin_secret_code') or '',
                'textin_endpoint': d.get('textin_endpoint') or '',
            }

# coding=utf-8
"""
    @project: maxkb
    @file: provider.py
    @desc: OCR Provider 抽象 + 工厂。

    设计：
      - OcrProvider 是一个简单 ABC，只有 recognize(image_bytes) -> str
      - 两种实现：
        * VisionLlmOcrProvider — 复用 models_provider 已接入的视觉大模型
        * LocalOcrProvider     — rapidocr-onnxruntime（lazy import，未安装时给清晰报错）
      - 通过 SystemSetting(type=OCR).meta 读 mode + model_id + workspace_id 来分发
"""
from abc import ABC, abstractmethod
from typing import Optional


class OcrError(Exception):
    """OCR 识别过程发生的可恢复错误。"""


class OcrConfigError(Exception):
    """OCR 配置缺失或不合法。前端应让用户先去系统设置完成配置。"""


class OcrProvider(ABC):
    @abstractmethod
    def recognize(self, image_bytes: bytes) -> str:
        """识别一张图片，返回文本。失败时可抛 OcrError；
        不应直接抛底层 SDK 的异常类，便于上层 catch。"""


# OCR 模式常量（同步前端 enum）
MODE_VISION_LLM = 'vision_model'
MODE_LOCAL = 'local'
MODE_TEXTIN = 'textin'
ALL_MODES = (MODE_VISION_LLM, MODE_LOCAL, MODE_TEXTIN)


# OCR 提示词：让视觉模型尽量"忠实抄写"而非"总结"
DEFAULT_OCR_PROMPT = (
    "请把图片中的所有可见正文文字完整、忠实地识别并输出，保持原始的段落结构和列表项。"
    "如果页面中包含表格，请把该表格输出为 GitHub 风格的 Markdown 表格："
    "用 | 分隔每一列，表头行下方紧跟一行 |---|---| 形式的分隔行，"
    "完整保留表格的每一行、每一列，不要遗漏或合并行列；"
    "非表格的文字仍按普通段落输出。"
    "请忽略页面背景的水印、印章底纹、以及页眉页脚处的水印文字，不要识别这些内容。"
    "不要做总结、解释、翻译或添加任何额外说明，只输出图片中的文字本身。"
    "确实模糊、无法辨认的部分用 [unclear] 占位。"
    "如果页面是空白页、或仅包含图片而没有任何文字，请输出空字符串。"
)


def get_ocr_provider(config: Optional[dict] = None) -> OcrProvider:
    """根据 OCR 系统配置返回对应 provider 实例。

    config 直接来自 OcrSettingSerializer.one()：
      {
        "mode": "vision_model" | "local",
        "model_id": "<uuid>",        # mode=vision_model 必填
        "workspace_id": "default",   # mode=vision_model 必填
        "prompt": "..."              # 可选，默认 DEFAULT_OCR_PROMPT
      }
    """
    if not config or not isinstance(config, dict):
        raise OcrConfigError("OCR 未配置：请先到「系统设置 → OCR 设置」选择视觉模型或启用本地 OCR")

    mode = config.get('mode')
    if mode not in ALL_MODES:
        raise OcrConfigError(f"OCR 配置无效：mode 必须是 {ALL_MODES} 之一，当前为 {mode!r}")

    if mode == MODE_VISION_LLM:
        model_id = config.get('model_id')
        workspace_id = config.get('workspace_id') or 'default'
        prompt = config.get('prompt') or DEFAULT_OCR_PROMPT
        if not model_id:
            raise OcrConfigError("OCR 配置不完整：选择了视觉大模型但未指定 model_id")
        # 延迟到这里再 import，避免循环依赖（provider.py 被 settings 链路扫到时）
        from common.handle.impl.ocr.vision_llm_provider import VisionLlmOcrProvider
        return VisionLlmOcrProvider(model_id=model_id, workspace_id=workspace_id, prompt=prompt)

    if mode == MODE_LOCAL:
        from common.handle.impl.ocr.local_provider import LocalOcrProvider
        return LocalOcrProvider(
            language=config.get('language') or 'ch',
        )

    if mode == MODE_TEXTIN:
        app_id = config.get('textin_app_id') or ''
        secret_code = config.get('textin_secret_code') or ''
        endpoint = config.get('textin_endpoint') or ''
        if not app_id or not secret_code:
            raise OcrConfigError(
                "OCR 配置不完整：选择了 TextIn 但未填 app_id / secret_code"
            )
        from common.handle.impl.ocr.textin_provider import TextinOcrProvider
        return TextinOcrProvider(
            app_id=app_id,
            secret_code=secret_code,
            endpoint=endpoint or None,
        )

    # 不会走到这里（已经被 ALL_MODES 校验拦住），保险起见
    raise OcrConfigError(f"未知 OCR 模式：{mode!r}")

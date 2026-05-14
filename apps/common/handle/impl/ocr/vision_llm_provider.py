# coding=utf-8
"""
    @project: maxkb
    @file: vision_llm_provider.py
    @desc: 视觉大模型 OCR provider。复用 models_provider 已接入的多模态模型
           （OpenAI gpt-4o, Anthropic, Gemini, 通义千问 vl, 智谱 glm-4v 等）。
"""
import base64
import concurrent.futures
import os
from imghdr import what

from langchain_core.messages import HumanMessage

from common.handle.impl.ocr.image_preprocess import preprocess_for_ocr
from common.handle.impl.ocr.provider import OcrProvider, OcrError, DEFAULT_OCR_PROMPT
from common.utils.logger import maxkb_logger

# Image preprocessing level applied before the model call. Env-gated so ops can
# switch to 'aggressive' (heavier watermark suppression) or 'off' without a
# code change. See image_preprocess.preprocess_for_ocr for the level semantics.
_OCR_PREPROCESS_LEVEL = os.environ.get('MAXKB_OCR_PREPROCESS_LEVEL', 'standard')

# Hard ceiling for a single-page vision-LLM OCR call. Some providers leave the
# HTTP connection hanging indefinitely on a problematic page instead of
# returning an error — without this wrapper that hangs the whole celery OCR
# task forever (observed: a 41-page scanned PDF stuck on page 22 for 10+ min).
# On timeout we raise OcrError so the per-page handler in pdf_split_handle
# logs-and-continues to the next page instead of blocking the entire document.
_OCR_INVOKE_TIMEOUT_SECONDS = 120


class VisionLlmOcrProvider(OcrProvider):
    def __init__(self, model_id: str, workspace_id: str = 'default', prompt: str = DEFAULT_OCR_PROMPT):
        self.model_id = model_id
        self.workspace_id = workspace_id
        self.prompt = prompt

    def recognize(self, image_bytes: bytes) -> str:
        if not image_bytes:
            return ''
        # 先做轻量预处理（灰度 + 自动对比度，可选水印抑制），提升识别质量。
        # preprocess_for_ocr 永不抛异常 —— 失败时原样返回输入字节。
        image_bytes = preprocess_for_ocr(image_bytes, level=_OCR_PREPROCESS_LEVEL)
        # 检测格式（PNG/JPEG/...），imghdr 返回 'png'/'jpeg' 等小写名
        img_format = what(None, image_bytes) or 'png'
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        data_url = f'data:image/{img_format};base64,{b64}'

        try:
            # 延迟 import 避免在 Django 启动早期触发 model provider 链路
            from models_provider.tools import get_model_instance_by_model_workspace_id
            model = get_model_instance_by_model_workspace_id(self.model_id, self.workspace_id)
        except Exception as e:
            maxkb_logger.error(f"OCR: failed to load vision model {self.model_id}: {e}")
            raise OcrError(f"加载视觉模型失败：{e}")

        message = HumanMessage(content=[
            {'type': 'text', 'text': self.prompt},
            {'type': 'image_url', 'image_url': {'url': data_url}},
        ])
        # model.invoke has no built-in timeout; a hung provider connection would
        # otherwise block the celery OCR task forever. Run it in a worker thread
        # and enforce a hard deadline.
        #
        # IMPORTANT: do NOT use `with ThreadPoolExecutor()` — its __exit__ calls
        # shutdown(wait=True), which blocks on the hung thread and silently
        # eats the timeout. We must shutdown(wait=False) so the OCR task can
        # move on to the next page while the dead thread is left to be reclaimed.
        _ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _future = _ex.submit(model.invoke, [message])
        try:
            response = _future.result(timeout=_OCR_INVOKE_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            maxkb_logger.error(
                f"OCR: vision model invoke timed out after {_OCR_INVOKE_TIMEOUT_SECONDS}s"
            )
            raise OcrError(f"视觉模型识别超时（{_OCR_INVOKE_TIMEOUT_SECONDS} 秒）")
        except Exception as e:
            maxkb_logger.error(f"OCR: vision model invoke failed: {e}")
            raise OcrError(f"视觉模型识别失败：{e}")
        finally:
            # wait=False: return immediately even if the worker thread is hung.
            _ex.shutdown(wait=False)

        # langchain AIMessage.content 可能是 str 或 list[dict]
        content = response.content if hasattr(response, 'content') else str(response)
        if isinstance(content, list):
            parts = []
            for chunk in content:
                if isinstance(chunk, dict):
                    parts.append(chunk.get('text', ''))
                else:
                    parts.append(str(chunk))
            content = '\n'.join(parts)
        return (content or '').strip()

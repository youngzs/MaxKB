# coding=utf-8
"""
    @project: maxkb
    @file: textin_provider.py
    @desc: 合合信息 TextIn xparse OCR provider。
           接口文档：https://docs.textin.com/xparse/v1/quickstart

    与 VisionLlmOcrProvider 的契约一致：recognize(image_bytes) -> str。
    pdf_split_handle 把扫描页渲染成 PNG bytes 后逐页调用本 provider；TextIn 返回
    Markdown 格式（自动识别表格 / 标题 / 段落），上层 _split_text_preserving_md_tables
    已能识别 Markdown 表格分隔行并走表格感知分块，无需改动。
"""
import concurrent.futures
import json
import os

import requests

from common.handle.impl.ocr.provider import OcrError, OcrProvider
from common.utils.logger import maxkb_logger

# TextIn 同步解析端点。异步端点（parse/async）适合超大文件批处理，但本 provider
# 的契约是"每张图片 / 每页 PNG 单独调用"，同步端点足够。
_TEXTIN_SYNC_URL = 'https://api.textin.com/api/v1/xparse/parse/sync'

# 单次同步调用的硬超时。TextIn 同步接口对单张图片通常 5-15 秒返回；超过这个
# 阈值说明远端卡住，我们不能让一页 OCR 把整个 PDF 任务挂死。
_TEXTIN_INVOKE_TIMEOUT_SECONDS = int(os.environ.get('MAXKB_TEXTIN_TIMEOUT', '120'))

# TextIn 默认开启的 capabilities。table 结构识别是核心收益（vs. 视觉 LLM 经常
# 把表格转成自然语言），title_tree 让正文层级保留下来（# / ## / ###）。
_DEFAULT_CAPABILITIES = {
    'include_table_structure': True,
    'title_tree': True,
}


class TextinOcrProvider(OcrProvider):
    """TextIn xparse OCR provider（同步模式）。

    config 来源 SystemSetting(OCR).meta：
      {
        "mode": "textin",
        "textin_app_id": "...",
        "textin_secret_code": "...",
        "textin_endpoint": "https://api.textin.com/api/v1/xparse/parse/sync"  # 可选
      }
    凭据永远只落库不进代码。
    """

    def __init__(self, app_id: str, secret_code: str, endpoint: str = None):
        if not app_id or not secret_code:
            raise OcrError('TextIn 凭据缺失：app_id / secret_code 不能为空')
        self.app_id = app_id
        self.secret_code = secret_code
        self.endpoint = endpoint or _TEXTIN_SYNC_URL

    def recognize(self, image_bytes: bytes) -> str:
        if not image_bytes:
            return ''

        headers = {
            'x-ti-app-id': self.app_id,
            'x-ti-secret-code': self.secret_code,
        }
        files = {
            'file': ('page.png', image_bytes, 'image/png'),
        }
        data = {
            'config': json.dumps({'capabilities': _DEFAULT_CAPABILITIES}),
        }

        # 与 vision_llm_provider 同样的做法：用一次性 ThreadPoolExecutor 包一层
        # 硬超时。requests 自己的 timeout 一般足够，但保留这层兜底，行为与
        # 其他 provider 一致，便于 pdf_split_handle 的 _is_rate_limit_error 等
        # 上层逻辑统一处理。
        _ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _future = _ex.submit(
            requests.post,
            self.endpoint,
            headers=headers,
            files=files,
            data=data,
            timeout=_TEXTIN_INVOKE_TIMEOUT_SECONDS,
        )
        try:
            response = _future.result(timeout=_TEXTIN_INVOKE_TIMEOUT_SECONDS + 5)
        except concurrent.futures.TimeoutError:
            maxkb_logger.error(
                f"TextIn OCR: request timed out after {_TEXTIN_INVOKE_TIMEOUT_SECONDS}s"
            )
            raise OcrError(f"TextIn 识别超时（{_TEXTIN_INVOKE_TIMEOUT_SECONDS} 秒）")
        except requests.exceptions.RequestException as e:
            maxkb_logger.error(f"TextIn OCR: request failed: {e}")
            raise OcrError(f"TextIn 网络调用失败：{e}")
        except Exception as e:
            maxkb_logger.error(f"TextIn OCR: unexpected error: {e}")
            raise OcrError(f"TextIn 识别失败：{e}")
        finally:
            _ex.shutdown(wait=False)

        # HTTP 层错误（5xx / 4xx）。429 / 限流相关错误带上 'rate limit' / '429' 关键词，
        # 上层 _is_rate_limit_error 能识别并走分钟级退避。
        if response.status_code != 200:
            text_snippet = (response.text or '')[:500]
            if response.status_code == 429:
                raise OcrError(f"TextIn rate limit (429): {text_snippet}")
            raise OcrError(
                f"TextIn HTTP {response.status_code}: {text_snippet}"
            )

        # 业务层错误：HTTP 200 但响应里 code != 200 / 200000 之类的。
        try:
            payload = response.json()
        except ValueError as e:
            raise OcrError(f"TextIn 响应不是合法 JSON：{e}; body={(response.text or '')[:500]}")

        # TextIn 成功码常见为 200（部分文档为 200000）。仅当存在 data.markdown 时按成功处理。
        code = payload.get('code')
        data_obj = payload.get('data') or {}
        markdown = data_obj.get('markdown') or ''

        if not markdown:
            # 没拿到 markdown，要么没识别到内容，要么真的失败 —— 用 code/message 区分。
            msg = payload.get('message') or payload.get('msg') or ''
            if code and code not in (200, 200000, 0):
                # 业务错误关键字命中限流时，上层会走分钟级退避（quota / rate limit 等）
                raise OcrError(f"TextIn code={code} message={msg}")
            # 真·空白页：返回空字符串，上层会跳过本页
            return ''

        return markdown.strip()

# coding=utf-8
"""
    @project: maxkb
    @Author：虎
    @file： text_split_handle.py
    @date：2024/3/27 18:19
    @desc:
"""
import io
import os
import re
import zipfile
from typing import List
from urllib.parse import urljoin

import uuid_utils.compat as uuid
from charset_normalizer import detect
from django.utils.translation import gettext_lazy as _

from common.handle.base_split_handle import BaseSplitHandle
from common.handle.impl.text.csv_split_handle import CsvSplitHandle
from common.handle.impl.text.doc_split_handle import DocSplitHandle
from common.handle.impl.text.html_split_handle import HTMLSplitHandle
from common.handle.impl.text.image_ocr_split_handle import ImageOcrSplitHandle
from common.handle.impl.text.pdf_split_handle import PdfSplitHandle
from common.handle.impl.text.text_split_handle import TextSplitHandle
from common.handle.impl.text.xls_split_handle import XlsSplitHandle
from common.handle.impl.text.xlsx_split_handle import XlsxSplitHandle
from common.utils.common import parse_md_image
from common.utils.logger import maxkb_logger
from knowledge.models import File


class FileBufferHandle:
    buffer = None

    def get_buffer(self, file):
        if self.buffer is None:
            self.buffer = file.read()
        return self.buffer


class _ZipEntryFile:
    """让 zip 内的条目"看起来像" Django UploadedFile。

    背景：`zip_ref.open()` 返回的 `ZipExtFile` 只有 `.read()`，没有 `.chunks()` /
    `.size` 等属性。但 `PdfSplitHandle.handle` 用 `file.chunks()` 写临时文件
    （参见 [pdf_split_handle.py:178](apps/common/handle/impl/text/pdf_split_handle.py:178)），
    `ImageOcrSplitHandle.support` 用 `.name.lower()` 等等。zip 里的所有
    PDF / 图片如果直接喂 `ZipExtFile` 都会因为 `AttributeError: 'ZipExtFile'
    object has no attribute 'chunks'` 而被 except Exception 静默吞掉 ——
    郎溪道其 zip 22 个条目里 14 个 PDF + 2 个 PNG + 4 目录 ≈ 18 个文件，
    只剩 4 个非 PDF/PNG 文件能进 KB（实测确认）。本类把 zip 条目封装成
    完整接口的文件对象，行为对齐顶层上传的 UploadedFile。
    """

    def __init__(self, raw_bytes: bytes, name: str):
        self._bytes = raw_bytes
        self.name = name
        self.size = len(raw_bytes)
        self._pos = 0

    def read(self, n=-1):
        if n is None or n < 0:
            data = self._bytes[self._pos:]
            self._pos = len(self._bytes)
        else:
            data = self._bytes[self._pos:self._pos + n]
            self._pos += len(data)
        return data

    def seek(self, offset, whence=0):
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        elif whence == 2:
            self._pos = len(self._bytes) + offset

    def tell(self):
        return self._pos

    def chunks(self, chunk_size=64 * 1024):
        # Django UploadedFile 风格的分块迭代器，PdfSplitHandle 写临时文件用
        old_pos = self._pos
        self._pos = 0
        try:
            while True:
                data = self.read(chunk_size)
                if not data:
                    break
                yield data
        finally:
            self._pos = old_pos


def _inject_zip_meta(item, relative_path: str, segments: list):
    """把 zip 内部路径写到 result item.meta —— 让 batch_save 末尾的
    auto_tag_documents 能据此识别 role / doc_type / path 标签，与"上传文件夹"
    路径一致行为。"""
    if item is None:
        return
    meta = dict(item.get('meta') or {})
    meta['relative_path'] = relative_path
    meta['path_segments'] = segments
    item['meta'] = meta


default_split_handle = TextSplitHandle()
split_handles = [
    HTMLSplitHandle(),
    DocSplitHandle(),
    PdfSplitHandle(),
    XlsxSplitHandle(),
    XlsSplitHandle(),
    CsvSplitHandle(),
    # 历史版本漏配 ImageOcrSplitHandle —— zip 里独立 PNG/JPG（非 docx 内嵌）
    # 落到 default_split_handle 把二进制当文本读，必崩；2026-05-25 修复。
    ImageOcrSplitHandle(),
    default_split_handle
]


def file_to_paragraph(file, pattern_list: List, with_filter: bool, limit: int, save_inner_image):
    get_buffer = FileBufferHandle().get_buffer
    for split_handle in split_handles:
        if split_handle.support(file, get_buffer):
            return split_handle.handle(file, pattern_list, with_filter, limit, get_buffer, save_inner_image)
    raise Exception(_('Unsupported file format'))


def is_valid_uuid(uuid_str: str):
    try:
        uuid.UUID(uuid_str)
    except ValueError:
        return False
    return True


def get_image_list(result_list: list, zip_files: List[str]):
    image_file_list = []
    for result in result_list:
        for p in result.get('content', []):
            content: str = p.get('content', '')
            image_list = parse_md_image(content)
            for image in image_list:
                search = re.search("\(.*\)", image)
                if search:
                    new_image_id = str(uuid.uuid7())
                    source_image_path = search.group().replace('(', '').replace(')', '')
                    source_image_path = source_image_path.strip().split(" ")[0]
                    image_path = urljoin(result.get('name'), '.' + source_image_path if source_image_path.startswith(
                        '/') else source_image_path)
                    if not zip_files.__contains__(image_path):
                        continue
                    if image_path.startswith('oss/file/') or image_path.startswith('oss/image/'):
                        image_id = image_path.replace('oss/file/', '').replace('oss/image/', '')
                        if is_valid_uuid(image_id):
                            image_file_list.append({'source_file': image_path,
                                                    'image_id': image_id})
                        else:
                            image_file_list.append({'source_file': image_path,
                                                    'image_id': new_image_id})
                            content = content.replace(source_image_path, f'./oss/file/{new_image_id}')
                            p['content'] = content
                    else:
                        image_file_list.append({'source_file': image_path,
                                                'image_id': new_image_id})
                        content = content.replace(source_image_path, f'./oss/file/{new_image_id}')
                        p['content'] = content

    return image_file_list


def get_image_list_by_content(name: str, content: str, zip_files: List[str]):
    image_file_list = []
    image_list = parse_md_image(content)
    for image in image_list:
        search = re.search("\(.*\)", image)
        if search:
            new_image_id = str(uuid.uuid7())
            source_image_path = search.group().replace('(', '').replace(')', '')
            source_image_path = source_image_path.strip().split(" ")[0]
            image_path = urljoin(name, '.' + source_image_path if source_image_path.startswith(
                '/') else source_image_path)
            if not zip_files.__contains__(image_path):
                continue
            if image_path.startswith('oss/file/') or image_path.startswith('oss/image/'):
                image_id = image_path.replace('oss/file/', '').replace('oss/image/', '')
                if is_valid_uuid(image_id):
                    image_file_list.append({'source_file': image_path,
                                            'image_id': image_id})
                else:
                    image_file_list.append({'source_file': image_path,
                                            'image_id': new_image_id})
                    content = content.replace(source_image_path, f'./oss/file/{new_image_id}')

            else:
                image_file_list.append({'source_file': image_path,
                                        'image_id': new_image_id})
                content = content.replace(source_image_path, f'./oss/file/{new_image_id}')

    return image_file_list, content


def get_file_name(file_name):
    try:
        file_name_code = file_name.encode('cp437')
        charset = detect(file_name_code)['encoding']
        return file_name_code.decode(charset)
    except Exception as e:
        return file_name


def filter_image_file(result_list: list, image_list):
    image_source_file_list = [image.get('source_file') for image in image_list]
    return [r for r in result_list if not image_source_file_list.__contains__(r.get('name', ''))]


class ZipSplitHandle(BaseSplitHandle):
    def handle(self, file, pattern_list: List, with_filter: bool, limit: int, get_buffer, save_image):
        if type(limit) is str:
            limit = int(limit)
        if type(with_filter) is str:
            with_filter = with_filter.lower() == 'true'
        buffer = get_buffer(file)
        bytes_io = io.BytesIO(buffer)
        result = []
        # 打开zip文件
        with zipfile.ZipFile(bytes_io, 'r') as zip_ref:
            # 获取压缩包中的文件名列表
            files = zip_ref.namelist()
            # 给每个 zip entry 单独存的 File row,稍后一次性 batch save
            source_files_to_save = []
            # 读取压缩包中的文件内容
            for entry_name in files:
                if entry_name.endswith('/') or entry_name.startswith('__MACOSX'):
                    continue
                try:
                    real_name = get_file_name(entry_name)
                    # 取最后一段作为"文件名"，保留全路径作为 meta；split handler 只用
                    # 文件名后缀决定 support()，不需要带 zip 内目录。
                    basename = real_name.replace('\\', '/').rsplit('/', 1)[-1]
                    with zip_ref.open(entry_name) as zf:
                        raw_bytes = zf.read()

                    # 关键:给每个 zip entry 一个独立的 File row,把"原始字节"持久化。
                    # 历史版本所有 zip 子文档共用 zip 自身的 source_file_id —— 异步
                    # OCR 任务 enqueue_ocr_if_pdf 检查"file_name.endswith('.pdf')"
                    # 永远 False(zip 后缀),OCR 永远不跑,扫描版 PDF 全部 0 字符。
                    # 给每个 entry 独立 File row 后:
                    #   1. enqueue_ocr_if_pdf 能识别 .pdf 后缀 → OCR 任务入队
                    #   2. _get_source_pdf_bytes 能拿到这个 PDF 的真实字节
                    #   3. "下载源文件" 也得到正确的单文件而不是整 zip
                    entry_file_id = uuid.uuid7()
                    source_files_to_save.append(File(
                        id=entry_file_id,
                        file_name=basename,
                        meta={'debug': False, 'content': raw_bytes},
                    ))

                    wrapped = _ZipEntryFile(raw_bytes, basename)
                    value = file_to_paragraph(wrapped, pattern_list, with_filter, limit, save_image)
                    # 给每个 result item 注入 path_segments meta —— Phase 2 自动打标会用
                    segments = [s for s in real_name.replace('\\', '/').split('/') if s]
                    if isinstance(value, list):
                        for item in value:
                            _inject_zip_meta(item, real_name, segments)
                            item['source_file_id'] = str(entry_file_id)
                        result.extend(value)
                    else:
                        _inject_zip_meta(value, real_name, segments)
                        value['source_file_id'] = str(entry_file_id)
                        result.append(value)
                except Exception as e:
                    # 历史版本是 `except Exception: pass` —— 任何条目失败都静默丢掉，
                    # 导致用户上传 22 个文件只看到 5 条进来还不知道为什么。现在改记
                    # warning，让运维能从日志里看出哪些条目失败。批量上传里"单条
                    # 失败"仍然不阻挡其他条目，但留下证据链。
                    maxkb_logger.warning(
                        f"ZipSplitHandle: skipping entry {entry_name!r}: {e!r}"
                    )
                    continue
            # batch 存所有 zip entry 的 File row —— 复用 save_image callback
            # (它的实现是通用的"按 meta['content'] 存 File",名字仅是历史命名)。
            # 任何存储失败都记 warning,不阻塞主流程;只是丢失了 source_file_id 链
            # → enqueue_ocr_if_pdf 退化到旧行为(zip 后缀检查失败,OCR 不跑)。
            if source_files_to_save:
                try:
                    save_image(source_files_to_save)
                except Exception as e:
                    maxkb_logger.warning(
                        f"ZipSplitHandle: failed to save per-entry source files: {e!r}"
                    )
            image_list = get_image_list(result, files)
            result = filter_image_file(result, image_list)
            image_mode_list = []
            for image in image_list:
                with zip_ref.open(image.get('source_file')) as f:
                    i = File(
                        id=image.get('image_id'),
                        file_name=os.path.basename(image.get('source_file')),
                        meta={'debug': False, 'content': f.read()}  # 这里的content是二进制数据
                    )
                    image_mode_list.append(i)
            save_image(image_mode_list)
        return result

    def support(self, file, get_buffer):
        file_name: str = file.name.lower()
        if file_name.endswith(".zip") or file_name.endswith(".ZIP"):
            return True
        return False

    def get_content(self, file, save_image):
        """
        从 zip 中提取并返回拼接的 md 文本，同时收集并保存内嵌图片（通过 save_image 回调）。
        使用 posixpath 来正确处理 zip 内部的路径拼接与规范化。
        """
        buffer = file.read() if hasattr(file, 'read') else None
        bytes_io = io.BytesIO(buffer) if buffer is not None else io.BytesIO(file)
        image_list = []
        content_parts = []

        with zipfile.ZipFile(bytes_io, 'r') as zip_ref:
            files = zip_ref.namelist()
            file_content_list = []
            for inner_name in files:
                if inner_name.endswith('/') or inner_name.startswith('__MACOSX'):
                    continue
                with zip_ref.open(inner_name) as zf:
                    try:
                        real_name = get_file_name(zf.name)
                    except Exception:
                        real_name = zf.name
                    # 为 split_handle 提供可重复读取的 file-like 对象
                    zf.name = real_name
                    get_buffer = FileBufferHandle().get_buffer
                    for split_handle in split_handles:
                        if split_handle.support(zf, get_buffer):
                            row = get_buffer(zf)
                            md_text = split_handle.get_content(io.BytesIO(row), save_image)
                            file_content_list.append({'content': md_text, 'name': real_name})
                            break
            for file_content in file_content_list:
                _image_list, content = get_image_list_by_content(file_content.get('name'), file_content.get("content"),
                                                                 files)
                content_parts.append(content)
                for image in _image_list:
                    image_list.append(image)

            # 将收集到的图片通过回调保存（一次性）
            if image_list:
                image_mode_list = []
                for image in image_list:
                    with zip_ref.open(image.get('source_file')) as f:
                        i = File(
                            id=image.get('image_id'),
                            file_name=os.path.basename(image.get('source_file')),
                            meta={'debug': False, 'content': f.read()}  # 这里的content是二进制数据
                        )
                        image_mode_list.append(i)
                save_image(image_mode_list)

        return '\n\n'.join(content_parts)

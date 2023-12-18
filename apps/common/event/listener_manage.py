# coding=utf-8
"""
    @project: maxkb
    @Author：虎
    @file： listener_manage.py
    @date：2023/10/20 14:01
    @desc:
"""
import os

import django.db.models
from blinker import signal
from django.db.models import QuerySet

from common.config.embedding_config import VectorStore, EmbeddingModel
from common.db.search import native_search, get_dynamics_model
from common.event.common import poxy
from common.util.file_util import get_file_content
from dataset.models import Paragraph, Status, Document
from embedding.models import SourceType
from smartdoc.conf import PROJECT_DIR


class ListenerManagement:
    embedding_by_problem_signal = signal("embedding_by_problem")
    embedding_by_paragraph_signal = signal("embedding_by_paragraph")
    embedding_by_dataset_signal = signal("embedding_by_dataset")
    embedding_by_document_signal = signal("embedding_by_document")
    delete_embedding_by_document_signal = signal("delete_embedding_by_document")
    delete_embedding_by_dataset_signal = signal("delete_embedding_by_dataset")
    delete_embedding_by_paragraph_signal = signal("delete_embedding_by_paragraph")
    delete_embedding_by_source_signal = signal("delete_embedding_by_source")
    enable_embedding_by_paragraph_signal = signal('enable_embedding_by_paragraph')
    disable_embedding_by_paragraph_signal = signal('disable_embedding_by_paragraph')
    init_embedding_model_signal = signal('init_embedding_model')

    @staticmethod
    def embedding_by_problem(args):
        VectorStore.get_embedding_vector().save(**args)

    @staticmethod
    @poxy
    def embedding_by_paragraph(paragraph_id):
        """
        向量化段落 根据段落id
        :param paragraph_id: 段落id
        :return: None
        """
        status = Status.success
        try:
            data_list = native_search(
                {'problem': QuerySet(get_dynamics_model({'problem.paragraph_id': django.db.models.CharField()})).filter(
                    **{'problem.paragraph_id': paragraph_id}),
                    'paragraph': QuerySet(Paragraph).filter(id=paragraph_id)},
                select_string=get_file_content(
                    os.path.join(PROJECT_DIR, "apps", "common", 'sql', 'list_embedding_text.sql')))
            # 删除段落
            VectorStore.get_embedding_vector().delete_by_paragraph_id(paragraph_id)
            # 批量向量化
            VectorStore.get_embedding_vector().batch_save(data_list)
        except Exception as e:
            status = Status.error
        QuerySet(Paragraph).filter(id=paragraph_id).update(**{'status': status})

    @staticmethod
    @poxy
    def embedding_by_document(document_id):
        """
        向量化文档
        :param document_id: 文档id
        :return: None
        """
        status = Status.success
        try:
            data_list = native_search(
                {'problem': QuerySet(get_dynamics_model({'problem.document_id': django.db.models.CharField()})).filter(
                    **{'problem.document_id': document_id}),
                    'paragraph': QuerySet(Paragraph).filter(document_id=document_id)},
                select_string=get_file_content(
                    os.path.join(PROJECT_DIR, "apps", "common", 'sql', 'list_embedding_text.sql')))
            # 删除文档向量数据
            VectorStore.get_embedding_vector().delete_by_document_id(document_id)
            # 批量向量化
            VectorStore.get_embedding_vector().batch_save(data_list)
        except Exception as e:
            status = Status.error
        # 修改状态
        QuerySet(Document).filter(id=document_id).update(**{'status': status})
        QuerySet(Paragraph).filter(document_id=document_id).update(**{'status': status})

    @staticmethod
    @poxy
    def embedding_by_dataset(dataset_id):
        """
        向量化知识库
        :param dataset_id: 知识库id
        :return: None
        """
        status = Status.success
        try:
            data_list = native_search(
                {'problem': QuerySet(get_dynamics_model({'problem.dataset_id': django.db.models.CharField()})).filter(
                    **{'problem.dataset_id': dataset_id}),
                    'paragraph': QuerySet(Paragraph).filter(dataset_id=dataset_id)},
                select_string=get_file_content(
                    os.path.join(PROJECT_DIR, "apps", "common", 'sql', 'list_embedding_text.sql')))
            # 删除知识库相关向量数据
            VectorStore.get_embedding_vector().delete_by_dataset_id(dataset_id)
            # 批量向量化
            VectorStore.get_embedding_vector().batch_save(data_list)
        except Exception as e:
            status = Status.error
        #  修改文档 以及段落的状态
        QuerySet(Document).filter(dataset_id=dataset_id).update(**{'status': status})
        QuerySet(Paragraph).filter(dataset_id=dataset_id).update(**{'status': status})

    @staticmethod
    def delete_embedding_by_document(document_id):
        VectorStore.get_embedding_vector().delete_by_document_id(document_id)

    @staticmethod
    def delete_embedding_by_dataset(dataset_id):
        VectorStore.get_embedding_vector().delete_by_dataset_id(dataset_id)

    @staticmethod
    def delete_embedding_by_paragraph(paragraph_id):
        VectorStore.get_embedding_vector().delete_by_paragraph_id(paragraph_id)

    @staticmethod
    def delete_embedding_by_source(source_id):
        VectorStore.get_embedding_vector().delete_by_source_id(source_id, SourceType.PROBLEM)

    @staticmethod
    def disable_embedding_by_paragraph(paragraph_id):
        VectorStore.get_embedding_vector().update_by_paragraph_id(paragraph_id, {'is_active': False})

    @staticmethod
    def enable_embedding_by_paragraph(paragraph_id):
        VectorStore.get_embedding_vector().update_by_paragraph_id(paragraph_id, {'is_active': True})

    @staticmethod
    @poxy
    def init_embedding_model(ags):
        EmbeddingModel.get_embedding_model()

    def run(self):
        #  添加向量 根据问题id
        ListenerManagement.embedding_by_problem_signal.connect(self.embedding_by_problem)
        #  添加向量 根据段落id
        ListenerManagement.embedding_by_paragraph_signal.connect(self.embedding_by_paragraph)
        #  添加向量 根据知识库id
        ListenerManagement.embedding_by_dataset_signal.connect(
            self.embedding_by_dataset)
        #  添加向量 根据文档id
        ListenerManagement.embedding_by_document_signal.connect(
            self.embedding_by_document)
        # 删除 向量 根据文档
        ListenerManagement.delete_embedding_by_document_signal.connect(self.delete_embedding_by_document)
        # 删除 向量 根据知识库id
        ListenerManagement.delete_embedding_by_dataset_signal.connect(self.delete_embedding_by_dataset)
        # 删除向量 根据段落id
        ListenerManagement.delete_embedding_by_paragraph_signal.connect(
            self.delete_embedding_by_paragraph)
        # 删除向量 根据资源id
        ListenerManagement.delete_embedding_by_source_signal.connect(self.delete_embedding_by_source)
        # 禁用段落
        ListenerManagement.disable_embedding_by_paragraph_signal.connect(self.disable_embedding_by_paragraph)
        # 启动段落向量
        ListenerManagement.enable_embedding_by_paragraph_signal.connect(self.enable_embedding_by_paragraph)
        # 初始化向量化模型
        ListenerManagement.init_embedding_model_signal.connect(self.init_embedding_model)

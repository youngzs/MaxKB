# coding=utf-8
"""
    @project: maxkb
    @Author：虎
    @file： base_search_dataset_step.py
    @date：2024/1/10 10:33
    @desc:
"""
import os
from typing import List, Dict

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from langchain_core.messages import HumanMessage
from rest_framework.utils.formatting import lazy_format

from application.chat_pipeline.I_base_chat_pipeline import ParagraphPipelineModel
from application.chat_pipeline.step.search_dataset_step.i_search_dataset_step import ISearchDatasetStep
from application.chat_pipeline.step.search_dataset_step.mmr import mmr_rerank
from application.chat_pipeline.step.search_dataset_step.query_split import SPLIT_PROMPT, parse_sub_queries
from common.config.embedding_config import VectorStore, ModelManage
from common.constants.permission_constants import RoleConstants
from common.database_model_manage.database_model_manage import DatabaseModelManage
from common.db.search import native_search
from common.utils.common import get_file_content
from common.utils.logger import maxkb_logger
from knowledge.models import Paragraph, Knowledge, Embedding
from knowledge.models import SearchMode
from maxkb.conf import PROJECT_DIR
from models_provider.models import Model
from models_provider.tools import (get_model, get_model_by_id, get_model_default_params,
                                   get_model_instance_by_model_workspace_id)


def reset_meta(meta):
    if not meta.get('allow_download', False):
        return {'allow_download': False}
    return meta


def get_embedding_id(knowledge_id_list):
    knowledge_list = QuerySet(Knowledge).filter(id__in=knowledge_id_list)
    if len(set([knowledge.embedding_model_id for knowledge in knowledge_list])) > 1:
        raise Exception(
            _("The vector model of the associated knowledge base is inconsistent and the segmentation cannot be recalled."))
    if len(knowledge_list) == 0:
        raise Exception(_("The knowledge base setting is wrong, please reset the knowledge base"))
    return knowledge_list[0].embedding_model_id


# ===========================================================================
# 检索自适应调优（A 档 top_n 自适应 + B 档 MMR 重排 + C 档 查询拆解）
# ---------------------------------------------------------------------------
# 背景：app 的 knowledge_setting.top_n 是写死常量，对几十~几百段落的大库召回
# 量不够；且纯相似度排序下，单文档的几十个雷同段落会霸占 top-N，把其他文档里
# 「唯一相关」的段落挤掉（典型：一份征信报告 41 段把执照/财报段落挤出召回）。
#
# A 档：top_n 按知识库 active 段落规模缩放，max(用户配置, 推导值) —— 只升不降，
#       永不低于用户显式配置值，零损害。
# B 档：MMR 多样性重排 —— 扩大候选池后按「相关性 vs 多样性」重排，压制雷同段落。
# C 档：查询拆解 —— 宽泛、跨多意图的问题拆成 N 个聚焦子查询，各自走 A+B 检索后
#       合并去重。解决「平均向量稀释」：宽问题 embedding 是多意图均值，对任何
#       单一意图都不强匹配，窄主题（财务/股权）会被稀释出召回。
# 三者叠加：C 解决多意图稀释、A 解决召回量、B 解决子查询内部冗余。
# 总开关 MMR_ENABLED / QUERY_SPLIT_ENABLED 可分别一键回退。
# ===========================================================================
MMR_ENABLED = True       # B 档总开关；False 时仅 A 档生效，回退纯相似度排序
MMR_POOL_FACTOR = 4      # 候选池规模 = effective_top_n × 该系数
MMR_LAMBDA = 0.5         # MMR 相关性权重（越大越偏相关、越小越偏多样）

QUERY_SPLIT_ENABLED = True   # C 档总开关；False 时回退单查询（A+B 不受影响）
MAX_SUB_QUERIES = 6          # 子查询数上限 —— 防止模型拆过细导致检索次数爆炸
MERGE_CAP = 30               # 多子查询合并去重后整体段落上限 —— 控制 context/token


def adaptive_top_n(configured_top_n, knowledge_id_list) -> int:
    """A 档：top_n 按知识库 active 段落数自适应。返回 max(用户配置, 推导值)。

    统计失败时退回用户原配置 —— 不让一个 count 查询影响检索主流程。
    """
    try:
        para_count = (QuerySet(Embedding)
                      .filter(knowledge_id__in=knowledge_id_list, is_active=True)
                      .values('paragraph_id').distinct().count())
    except Exception as e:  # noqa: BLE001
        maxkb_logger.warning(f'[search] adaptive_top_n count failed: {e}')
        return configured_top_n
    if para_count <= 10:
        recommended = 5
    elif para_count <= 50:
        recommended = 10
    elif para_count <= 200:
        recommended = 20
    else:
        recommended = 30
    return max(configured_top_n or 0, recommended)


def mmr_filter(candidate_list, query_embedding, k: int):
    """B 档：对候选池做 MMR 重排，返回 k 条检索结果 dict。

    candidate_list 是 vector.query() 的返回（dict 列表，含 paragraph_id 但
    不含向量）。这里按 paragraph_id 批量补取 Embedding 向量再交给 mmr_rerank。

    退化保护：任何异常 / 向量补取不全 → 退回「按原相似度顺序取前 k」，
    MMR 永远不能让检索整体失败。
    """
    if candidate_list is None:
        return None
    if len(candidate_list) <= k:
        return candidate_list
    try:
        para_ids = [str(c.get('paragraph_id')) for c in candidate_list]
        emb_map = {}
        for row in (QuerySet(Embedding)
                    .filter(paragraph_id__in=para_ids)
                    .values('paragraph_id', 'embedding')):
            pid = str(row.get('paragraph_id'))
            # 一个段落可能有多条 embedding（分块）—— 取第一条作代表即可
            if pid not in emb_map and row.get('embedding') is not None:
                emb_map[pid] = row.get('embedding')
        enriched = [{'_row': c, 'embedding': emb_map[str(c.get('paragraph_id'))]}
                    for c in candidate_list
                    if str(c.get('paragraph_id')) in emb_map]
        if len(enriched) <= k:
            return candidate_list[:k]
        ranked = mmr_rerank(query_embedding, enriched, k, MMR_LAMBDA)
        return [item['_row'] for item in ranked]
    except Exception as e:  # noqa: BLE001
        maxkb_logger.warning(f'[search] MMR rerank failed, fallback to score order: {e}')
        return candidate_list[:k]


def split_query(query_text: str, manage) -> List[str]:
    """C 档：用 workspace 的 chat 模型把宽泛问题拆成 1~N 个聚焦子查询。

    裁判门：是否拆、拆几个交给 LLM 自身判断 —— 简单问题它原样返回 1 个子查询
    （等于不拆），一次调用兼任「判断 + 拆解」。返回 1 个时调用方走单查询路径。

    退化保护：开关关闭 / 无 chat 模型 / 调用异常 / 解析失败 —— 一律返回
    [query_text]，绝不让拆解失败阻断检索。chat 模型取自 manage.context 的
    model_id（app 的对话模型，与检索用的 embedding 模型不同）。
    """
    if not QUERY_SPLIT_ENABLED:
        return [query_text]
    try:
        model_id = manage.context.get('model_id') if manage is not None else None
        workspace_id = manage.context.get('workspace_id') if manage is not None else None
        if model_id is None:
            return [query_text]
        chat_model = get_model_instance_by_model_workspace_id(model_id, workspace_id)
        if chat_model is None:
            return [query_text]
        prompt = SPLIT_PROMPT.replace('{max}', str(MAX_SUB_QUERIES)).replace('{question}', query_text)
        response = chat_model.invoke([HumanMessage(content=prompt)])
        sub_queries = parse_sub_queries(response.content, query_text, MAX_SUB_QUERIES)
        if len(sub_queries) > 1:
            maxkb_logger.info(f'[search] query split into {len(sub_queries)} sub-queries: {sub_queries}')
        return sub_queries
    except Exception as e:  # noqa: BLE001
        maxkb_logger.warning(f'[search] query split failed, fallback to single query: {e}')
        return [query_text]


def merge_embedding_lists(result_lists: List, cap: int) -> List[Dict]:
    """C 档：合并多个子查询的检索结果。

    按 paragraph_id 去重，同一段落跨子查询命中时取 comprehensive_score 最高的
    那一行；再按 comprehensive_score 降序整体截断到 cap 段。

    入参 result_lists 里的元素可能是 None / 空列表（子查询无召回）—— 跳过即可。
    """
    best: Dict[str, Dict] = {}
    for embedding_list in result_lists:
        if not embedding_list:
            continue
        for row in embedding_list:
            pid = str(row.get('paragraph_id'))
            score = row.get('comprehensive_score') or 0
            if pid not in best or score > (best[pid].get('comprehensive_score') or 0):
                best[pid] = row
    merged = sorted(best.values(), key=lambda r: r.get('comprehensive_score') or 0, reverse=True)
    return merged[:cap]


class BaseSearchDatasetStep(ISearchDatasetStep):

    def execute(self, problem_text: str, knowledge_id_list: list[str], exclude_document_id_list: list[str],
                exclude_paragraph_id_list: list[str], top_n: int, similarity: float, padding_problem_text: str = None,
                search_mode: str = None,
                workspace_id=None,
                manage=None,
                **kwargs) -> List[ParagraphPipelineModel]:
        get_knowledge_list_of_authorized = DatabaseModelManage.get_model('get_knowledge_list_of_authorized')
        chat_user_type = manage.context.get('chat_user_type')
        if get_knowledge_list_of_authorized is not None and RoleConstants.CHAT_USER.value.name == chat_user_type:
            knowledge_id_list = get_knowledge_list_of_authorized(manage.context.get('chat_user_id'),
                                                                 knowledge_id_list)
        if len(knowledge_id_list) == 0:
            return []
        exec_problem_text = padding_problem_text if padding_problem_text is not None else problem_text
        model_id = get_embedding_id(knowledge_id_list)
        model = get_model_by_id(model_id, workspace_id)
        if model.model_type != "EMBEDDING":
            raise Exception(_("Model does not exist"))
        self.context['model_name'] = model.name
        default_params = get_model_default_params(model)
        embedding_model = ModelManage.get_model(model_id, lambda _id: get_model(model, **{**default_params}))
        vector = VectorStore.get_embedding_vector()
        # A 档：top_n 按知识库段落规模自适应（只升不降）
        effective_top_n = adaptive_top_n(top_n, knowledge_id_list)
        # C 档：宽泛问题拆成多个聚焦子查询（简单问题原样返回 1 个 = 不拆）
        sub_queries = split_query(exec_problem_text, manage)
        self.context['sub_query_list'] = sub_queries
        if len(sub_queries) == 1:
            # 单查询：行为与 A+B 完全一致 —— 裁判门保证简单问题不触发多路检索
            embedding_list = self._retrieve_one(sub_queries[0], embedding_model, vector,
                                                knowledge_id_list, exclude_document_id_list,
                                                exclude_paragraph_id_list, effective_top_n,
                                                similarity, search_mode)
        else:
            # 多子查询：每个子查询各走 A+B 检索管线，结果合并去重并 cap 到 MERGE_CAP
            result_lists = [
                self._retrieve_one(sub_query, embedding_model, vector, knowledge_id_list,
                                   exclude_document_id_list, exclude_paragraph_id_list,
                                   effective_top_n, similarity, search_mode)
                for sub_query in sub_queries
            ]
            embedding_list = merge_embedding_lists(result_lists, MERGE_CAP)
        if embedding_list is None:
            return []
        paragraph_list = self.list_paragraph(embedding_list, vector)
        result = [self.reset_paragraph(paragraph, embedding_list) for paragraph in paragraph_list]
        return result

    @staticmethod
    def _retrieve_one(query_text, embedding_model, vector, knowledge_id_list,
                      exclude_document_id_list, exclude_paragraph_id_list,
                      effective_top_n, similarity, search_mode):
        """单条查询的检索：embed → 向量检索 → B 档 MMR 重排，返回 embedding_list。

        effective_top_n 由 A 档在外层算好后传入。MMR 关闭时直接返回向量检索结果。
        C 档多子查询时对每个子查询各调一次本方法。
        """
        embedding_value = embedding_model.embed_query(query_text)
        if MMR_ENABLED:
            # B 档：扩大候选池 → MMR 重排到 effective_top_n。
            # 候选池多召回，让"分数没那么炸但来自不同文档"的段落有机会进池，
            # 再靠 MMR 的多样性把它们提到最终结果里。
            candidate_list = vector.query(query_text, embedding_value, knowledge_id_list, None,
                                          exclude_document_id_list, exclude_paragraph_id_list, True,
                                          effective_top_n * MMR_POOL_FACTOR, similarity,
                                          SearchMode(search_mode))
            return mmr_filter(candidate_list, embedding_value, effective_top_n)
        return vector.query(query_text, embedding_value, knowledge_id_list, None,
                            exclude_document_id_list, exclude_paragraph_id_list, True,
                            effective_top_n, similarity, SearchMode(search_mode))

    @staticmethod
    def reset_paragraph(paragraph: Dict, embedding_list: List) -> ParagraphPipelineModel:
        filter_embedding_list = [embedding for embedding in embedding_list if
                                 str(embedding.get('paragraph_id')) == str(paragraph.get('id'))]
        if filter_embedding_list is not None and len(filter_embedding_list) > 0:
            find_embedding = filter_embedding_list[-1]
            return (ParagraphPipelineModel.builder()
                    .add_paragraph(paragraph)
                    .add_similarity(find_embedding.get('similarity'))
                    .add_comprehensive_score(find_embedding.get('comprehensive_score'))
                    .add_knowledge_name(paragraph.get('knowledge_name'))
                    .add_knowledge_type(paragraph.get('knowledge_type'))
                    .add_document_name(paragraph.get('document_name'))
                    .add_hit_handling_method(paragraph.get('hit_handling_method'))
                    .add_directly_return_similarity(paragraph.get('directly_return_similarity'))
                    .add_meta(reset_meta(paragraph.get('meta')))
                    .build())

    @staticmethod
    def get_similarity(paragraph, embedding_list: List):
        filter_embedding_list = [embedding for embedding in embedding_list if
                                 str(embedding.get('paragraph_id')) == str(paragraph.get('id'))]
        if filter_embedding_list is not None and len(filter_embedding_list) > 0:
            find_embedding = filter_embedding_list[-1]
            return find_embedding.get('comprehensive_score')
        return 0

    @staticmethod
    def list_paragraph(embedding_list: List, vector):
        paragraph_id_list = [row.get('paragraph_id') for row in embedding_list]
        if paragraph_id_list is None or len(paragraph_id_list) == 0:
            return []
        paragraph_list = native_search(QuerySet(Paragraph).filter(id__in=paragraph_id_list),
                                       get_file_content(
                                           os.path.join(PROJECT_DIR, "apps", "application", 'sql',
                                                        'list_knowledge_paragraph_by_paragraph_id.sql')),
                                       with_table_name=True)
        # 如果向量库中存在脏数据 直接删除
        if len(paragraph_list) != len(paragraph_id_list):
            exist_paragraph_list = [row.get('id') for row in paragraph_list]
            for paragraph_id in paragraph_id_list:
                if not exist_paragraph_list.__contains__(paragraph_id):
                    vector.delete_by_paragraph_id(paragraph_id)
        # 如果存在直接返回的则取直接返回段落
        hit_handling_method_paragraph = [paragraph for paragraph in paragraph_list if
                                         (paragraph.get(
                                             'hit_handling_method') == 'directly_return' and BaseSearchDatasetStep.get_similarity(
                                             paragraph, embedding_list) >= paragraph.get(
                                             'directly_return_similarity'))]
        if len(hit_handling_method_paragraph) > 0:
            # 找到评分最高的
            return [sorted(hit_handling_method_paragraph,
                           key=lambda p: BaseSearchDatasetStep.get_similarity(p, embedding_list))[-1]]
        return paragraph_list

    def get_details(self, manage, **kwargs):
        step_args = self.context.get('step_args') or {}

        return {
            'status': self.status,
            'err_message': self.err_message,
            'step_type': 'search_step',
            'paragraph_list': [row.to_dict() for row in (self.context.get('paragraph_list') or [])],
            'run_time': self.context.get('run_time') or 0,
            'problem_text': step_args.get(
                'padding_problem_text') if 'padding_problem_text' in step_args else step_args.get('problem_text'),
            'sub_query_list': self.context.get('sub_query_list'),
            'model_name': self.context.get('model_name'),
            'message_tokens': 0,
            'answer_tokens': 0,
            'cost': 0
        }

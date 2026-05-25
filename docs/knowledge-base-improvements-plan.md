# 知识库三项改进 实施计划

> 版本：v1.0
> 状态：**Phase 1 / 2 / 3 全部交付**（代码完成 + 本地 lint/type-check 干净 + Phase 1 TextIn 凭据已实测）
> 创建：2026-05-25
> 范围：融资材料知识库的三项痛点 —— ① PDF OCR 质量、② 财务数据幻觉、③ 目录结构丢失

## 交付清单（按 Phase）

### Phase 1 — TextIn OCR provider 接入 ✅
- `apps/common/handle/impl/ocr/textin_provider.py`（新增）：同步端点 `https://api.textin.com/api/v1/xparse/parse/sync` + 120s 硬超时 + 限流关键词命中复用上游分钟级退避
- `apps/common/handle/impl/ocr/provider.py`：新增 `MODE_TEXTIN`，工厂分发
- `apps/system_manage/serializers/ocr_setting.py`：配置 schema 新增 `textin_app_id` / `textin_secret_code` / `textin_endpoint`
- `ui/src/views/system-setting/ocr/index.vue`：「系统设置 → OCR 设置」增加 TextIn 选项 + 凭据输入
- **实测**：用用户提供的凭据 + 800x200 合成 PNG 跑通同步 API，返回 markdown OK

### Phase 2 — 目录结构上传 + 标签过滤（A 路）✅
- `apps/knowledge/serializers/document_auto_tag.py`（新增）：纯规则识别 `role` / `path` / `doc_type` 标签，复用已有的 `Tag` / `DocumentTag` 表 —— **零数据库迁移**
- `apps/knowledge/serializers/document.py`：
  - `DocumentInstanceSerializer` 加 `meta` 字段
  - `DocumentSplitRequest` 加 `relative_paths` 字段
  - `Split.parse` 把 webkitdirectory / zip 的相对路径写到结果 meta
  - `batch_save` 末尾调用 `auto_tag_documents`
- `apps/knowledge/views/document.py`：`Split.post` 接收 `relative_paths[]`
- `apps/application/flow/step_node/search_knowledge_node/`：`tag_filter` 参数 + `_tag_filter_to_document_ids` 查询
- 前端：
  - `ui/src/views/document/upload/SetRules.vue`：上传时附 `file.raw.webkitRelativePath`
  - `ui/src/views/document/UploadDocument.vue`：batch_save payload 透传 `meta`
  - `ui/src/workflow/nodes/search-knowledge-node/index.vue`：知识库检索节点新增「标签过滤」key/value 列表
  - `ui/src/workflow/common/template.ts`：默认模板加 `tag_filter: []`

### Phase 3 — 财务结构化 + 确定性计算 ✅
- 数据模型：`apps/knowledge/models/financial.py`（新增）+ migration `0009_financial_statement_and_fact.py`
  - `FinancialStatement`（document, statement_type, period, unit, raw_table_md, ...）
  - `FinancialFact`（statement, line_item, line_item_normalized, value, parent_line_item, indent_level）
- 抽取器：`apps/knowledge/services/financial_extractor.py`
  - 关键词识别报表类型（资产负债 / 利润 / 现金流量）
  - 别名表归一化科目（货币资金 / 现金及现金等价物 → 货币资金，等）
  - 表头识别期间（年度 / 季度 / 月度）
  - 数字解析（千分位 / 负号 / 括号负数 / 全角空格）
  - 单位识别（元 / 万元 / 千元 / 百万元 / 亿元）
  - 已用真实"盐城保安"数据回归通过：2024 货币资金 = 7,235,360.45 ✓
- 自动抽取 hook：`apps/knowledge/services/financial_auto_extract.py`
  - 在 `batch_save` 末尾跑；对带 `doc_type=财务报表/审计报告` 标签的文档生效
  - 失败吞掉异常，永不阻塞上传
- 工作流节点：`apps/application/flow/step_node/financial_calc_node/`
  - 5 个确定性函数：`get_fact` / `compare_periods` / `ratio` / `sum_items` / `list_facts`
  - 单位统一折算到「元」后再算
  - 每个返回值带 `sources: [document_id, ...]` 便于回答时引用
  - 返回 `data` 字段是自然语言摘要，供 ai_chat 节点引用
- 节点注册：`apps/application/flow/step_node/__init__.py` + `ui/src/enums/application.ts` + `ui/src/workflow/common/data.ts`
- 前端编辑器：`ui/src/workflow/nodes/financial-calc-node/{index.ts, index.vue}`

### 未在本次交付（按用户后续优先级再做）
- **Intent routing 模板**：admin 在工作流编辑器里手工拉 `intent_node`（命中"算/对比/趋势"关键词）→ `financial_calc_node`；目前没有提供"开箱即用"的财务问答应用模板
- **Chat-entry 运行时标签 picker**：用户在问答输入框上方选标签 → 自动注入 `tag_filter` 到节点；目前 `tag_filter` 在工作流编辑器里"硬编码"（admin 创建多个应用各自预设过滤条件）
- **现金流量表抽取**：抽取器结构上支持，但别名表只补到资产负债 + 利润，现金流量科目偏弱，需要补关键词
- **跨期一致性校验**：资产 = 负债 + 所有者权益 自动核对，发现差异时打 warning

---

## 一、背景

当前知识库针对"融资材料"场景（参考：`H:\var\wulimin\盐城市保安服务有限公司`），暴露三个独立但相互加分的问题：

| # | 痛点 | 现状 | 期望 |
|---|------|------|------|
| 1 | PDF OCR 效果 | `local`（rapidocr）+ `vision_model`（视觉大模型）两档，扫描页质量不稳定，表格识别尤其差 | 接入 Textin xparse 作为商用档，表格/版面保真度提一档 |
| 2 | 财务数字幻觉 | 财务报表 → OCR → 切段 → 向量召回 → 大模型读段落"算"指标，常出错 | 数字结构化落库，"算"由 Python 干，大模型只做"问什么、答什么" |
| 3 | 目录结构丢失 | 上传以文件为最小单位，`H:\var\wulimin\...\借款人资料\xxx` 这种语义层级丢光，问答只能向量召回 | 上传保留路径，沉淀到 `Tag/DocumentTag`（已有表），问答时按"借款人/反担保人/财务报表/征信报告"等标签过滤 |

三件事可以**独立交付**。Phase 1（Textin）的表格 markdown 输出会显著降低 Phase 3 的"识别"成本，所以排在最前。

---

## 二、阶段总览

| 阶段 | 内容 | 估时 | 依赖 | 验收 |
|------|------|------|------|------|
| **Phase 1** | Textin OCR provider 接入 | 1-2 天 | 无 | 系统设置新增 Textin 选项，PDF 走 Textin 出 Markdown + 表格，扫描件实测对比 |
| **Phase 2** | 目录结构 / 标签过滤（A 路） | 2-3 天 | 无（与 Phase 1 并行可做） | zip/文件夹批量上传保留路径 → `Tag` 入库；问答前端按标签筛选；`search_knowledge_node` 支持 `tag_filter` |
| **Phase 3** | 财务数据结构化 + 确定性计算 | 5-7 天 | Phase 1（表格质量）+ Phase 2（"财务报表"标签定位主体） | 资产负债表/利润表数字进结构化表；新增 `financial_calc` 工具节点；典型问答（流动比率/资产负债率/同比）走计算路径而非 LLM 算 |

---

## 三、Phase 1 — Textin OCR Provider 接入

### 3.1 现状

- OCR 抽象：[apps/common/handle/impl/ocr/provider.py](apps/common/handle/impl/ocr/provider.py)
- 已有两档：`MODE_VISION_LLM`、`MODE_LOCAL`
- 配置来源：`SystemSetting(type=OCR).meta` → `OcrSettingSerializer.one()`
- PDF 调用方：[pdf_split_handle.py:_try_ocr_empty_pages](apps/common/handle/impl/text/pdf_split_handle.py#L284)（扫描页 fallback，已支持并发 + 限流退避）

### 3.2 改动

| 文件 | 改动 | 说明 |
|------|------|------|
| `apps/common/handle/impl/ocr/textin_provider.py` | **新增** | `class TextinOcrProvider(OcrProvider)`，调 `https://api.textin.com/ai/service/v1/pdf_to_markdown`（按图片单页）或 xparse 同步接口；返回 markdown |
| `apps/common/handle/impl/ocr/provider.py` | 加 `MODE_TEXTIN = 'textin'`，`get_ocr_provider` 加分支 | 同步前端 enum |
| `apps/system_manage/serializers/ocr_setting.py` | 配置 schema 增加 `app_id` / `secret_code` / `endpoint` 字段 | 凭据**只**落库，不进代码 |
| `ui/src/views/system/ocr/` | OCR 设置页加 Textin 选项 | UI 三选一 |
| `installer/...` 或 README | 文档说明凭据如何配置 | — |

### 3.3 关键设计点

- **不绕开现有 fallback 链路**：Textin 仍走 `_try_ocr_empty_pages`，输入是 PNG（pymupdf 渲染的单页），输出是文本/markdown，并发、重试、限流退避全部沿用。Textin 自己的限流（429 / quota）触发时，`_is_rate_limit_error` 已经能命中"`rate limit`"/`429`/`quota`" 这些关键词，无需改。
- **表格质量直接受益**：Textin 直接吐 Markdown 表格，[pdf_split_handle.py:_split_text_preserving_md_tables](apps/common/handle/impl/text/pdf_split_handle.py#L48) 已经能识别 `| --- |` 分隔行并走表格感知分块（每块带表头）—— **不需要改**。
- **错误兜底**：Textin 不可用时不自动降级（避免静默劣化）；若用户希望"Textin 失败回退本地"，下一版加一个 `fallback_mode` 字段。

### 3.4 验收

- 拿 `H:\var\wulimin\盐城市保安服务有限公司\` 下一份扫描版 PDF（含表格），对比 Textin vs 当前 vision_model 的：
  - 字符数（应基本持平或更多）
  - 表格行/列完整度（人工对比 3 个表格）
  - 单页耗时（Textin 同步调用一般 ≤ vision_llm 的一半）
- 知识库 chat-entry 实测："企业概况"类问答召回质量不降。

---

## 四、Phase 2 — 目录结构 / 标签过滤（A 路）

### 4.1 现状

- `Document.meta` 是 JSONField（[knowledge.py:195](apps/knowledge/models/knowledge.py#L195)）—— path_segments 直接进，零迁移。
- `Tag(knowledge_id, key, value)` 和 `DocumentTag(document_id, tag_id)` 已存在（[knowledge.py:210-237](apps/knowledge/models/knowledge.py#L210-L237)），unique key-value 组合 —— **零数据库迁移**，直接复用。
- 检索入口 [base_search_knowledge_node.execute](apps/application/flow/step_node/search_knowledge_node/impl/base_search_knowledge_node.py#L76) 已接 `knowledge_id_list` —— 加一个 `tag_filter` 参数即可在 SQL 层过滤。

### 4.2 改动

#### 后端

| 文件 | 改动 |
|------|------|
| `apps/knowledge/serializers/document.py` | 上传 serializer 接受 `relative_path` 字段（来自前端 `webkitdirectory` 或解压 zip 后的相对路径） |
| `apps/knowledge/views/document.py` | 新增"批量上传（含路径）"端点：接受 zip 或多文件 + 路径数组；保存 `Document.meta.path_segments = [...]` |
| `apps/knowledge/serializers/document.py`（同上） | 上传后自动写 `Tag/DocumentTag`：每一级目录写一个 `(key='path', value='借款人资料')`、`(key='path', value='盐城市保安服务有限公司')`，以及一个汇总键 `(key='role', value='借款人' / '反担保人')`（按一级目录名规则映射，可配置） |
| `apps/application/flow/step_node/search_knowledge_node/i_search_knowledge_node.py` | 节点参数 schema 增加 `tag_filter: [{key, value}]` 列表（AND 关系） |
| `apps/application/flow/step_node/search_knowledge_node/impl/base_search_knowledge_node.py` | `execute` 接收 `tag_filter`；在 `Document` 查询前先 `DocumentTag.objects.filter(tag__key=..., tag__value=...).values('document_id')` 取交集，传给 paragraph 召回 |
| `apps/knowledge/sql/` | 如果走 native sql 召回，在 SQL 里加一个 `INNER JOIN document_tag ON ...` 子句 |

#### 前端

| 文件 | 改动 |
|------|------|
| `ui/src/views/document/UploadDocument.vue` | `<input type="file" webkitdirectory>` 选项；或拖拽 zip 自动解压（前端用 `jszip`，把 entries 转成 `File` + `relative_path` 数组上传） |
| `ui/src/views/document/index.vue` | 文档列表加"路径"列展示 `meta.path_segments` |
| `ui/src/views/chat-entry/` 或应用配置页 | 检索节点配置 UI 增加"标签过滤"控件（多选 key-value） |
| `ui/src/components/ai-chat/` | 问答前可选"按标签筛选"chip（如"只问反担保人"） |

### 4.3 标签 schema 约定

```yaml
# 一级目录 → role
role:
  - 借款人
  - 反担保人
  - 担保人
  - 其他

# 全路径分段 → path（多个 path 标签 = 出现在该层级下）
path:
  - 借款人资料
  - 盐城市保安服务有限公司
  - 反担保主体
  - ...

# 文件名规则识别 → doc_type（Phase 2.5 可加，正则匹配文件名）
doc_type:
  - 营业执照
  - 征信报告
  - 财务报表
  - 章程
  - 担保业务调查报告
```

`role` / `doc_type` 的规则配置进一个 yaml 或 SystemSetting，不写死。

### 4.4 验收

- 用 `H:\var\wulimin\盐城市保安服务有限公司\` zip 上传，文档列表能看到"路径"列；`Tag` 表能查到 `role=借款人` 等记录。
- 问答页选择"只问反担保人" → 召回的段落全部来自反担保人目录下的文档。
- 现有不带 `tag_filter` 的应用行为不变（向后兼容）。

---

## 五、Phase 3 — 财务数据结构化 + 确定性计算

> 依赖 Phase 1（Textin 的表格输出质量）+ Phase 2（`doc_type=财务报表`、`role=借款人` 等标签定位主体）。

### 5.1 设计原则

- **识别和计算解耦**：识别（提数）和计算（用数）是两件事，分别做才不会被 LLM 的"幻觉"污染。
- **结构化 = 第二份事实**：原始段落继续向量化（保留可解释性），结构化数据并存作为"权威数字"。
- **最小可行集**：只覆盖资产负债表 + 利润表的高频科目；现金流量表 Phase 3.5 再做。

### 5.2 数据模型

新增表（在 `apps/knowledge/models/` 或新建 `apps/knowledge/models/financial.py`）：

```python
class FinancialStatement(AppModelMixin):
    """一份财务报表 = 一个文档里的一张表"""
    id = UUID
    document = FK(Document)
    statement_type = Choice('balance_sheet' | 'income_statement' | 'cash_flow')
    period = CharField  # '2023' / '2024Q1' / '2024-12'
    period_type = Choice('annual' | 'quarter' | 'month')
    entity_name = CharField  # '盐城市保安服务有限公司'
    unit = CharField  # '元' / '万元'
    raw_table_md = TextField  # 原始 markdown 表格,便于回溯
    extracted_at = DateTime
    extractor_version = CharField  # 'v1.0',便于以后重抽

class FinancialFact(AppModelMixin):
    """单一科目数字"""
    id = UUID
    statement = FK(FinancialStatement)
    line_item = CharField  # '货币资金' / '应收账款' / '主营业务收入'
    line_item_normalized = CharField  # '货币资金'（去后缀、统一别名）
    value = DecimalField  # 始终存"元",unit 在 statement 层
    parent_line_item = CharField(nullable)  # '流动资产合计' 之类的归属
    indent_level = Integer  # 缩进层级,辅助识别"明细 vs 合计"
```

### 5.3 抽取流程

```
Document(type=财务报表, Phase 2 标签命中)
  → Textin 输出 markdown table
  → FinancialExtractor.extract(md_table):
       1) 表头年份识别 → period 列表
       2) 行首科目名 → normalize（对照内置别名表：'货币资金'/'现金及现金等价物' 等）
       3) statement_type 分类（按行首关键词：'流动资产'→balance_sheet,'主营业务收入'→income_statement）
       4) value 解析（处理千分位、负号"-"/"()"、单位）
  → FinancialStatement + FinancialFact 入库
```

抽取器：[apps/knowledge/services/financial_extractor.py](apps/knowledge/services/financial_extractor.py)（新增）。**纯 Python + 规则 + 别名表**，不依赖 LLM。LLM 只在"行首科目无法 normalize 时"作 fallback（可选，Phase 3.5）。

### 5.4 计算工具

新增 workflow 节点：[apps/application/flow/step_node/financial_calc_node/](apps/application/flow/step_node/financial_calc_node/)

暴露的确定性函数（最小集）：

| 函数 | 入参 | 出参 |
|------|------|------|
| `get_fact` | entity, period, line_item | 数字 + 单位 + 来源 doc_id |
| `compare_periods` | entity, periods=[...], line_item | 各期数字 + 同比/环比 |
| `ratio` | entity, period, numerator, denominator | 比率（如流动比率 = 流动资产 / 流动负债） |
| `sum_items` | entity, period, line_items=[...] | 求和 |
| `list_facts` | entity, period | 该期所有科目 + 数字 |

每个函数返回结构化结果 + **数字来源**（doc_id + statement_id + 段落 id），供回答时引用。

### 5.5 路由

在 Agent / chat pipeline 里加意图识别（可复用现有的 `intent_node`）：

```
question
  ├─ 命中"算/对比/趋势/比率/同比/环比/多少/总额"等关键词
  │     → financial_calc_node（确定性计算）→ 拼答案
  └─ 其他
        → search_knowledge_node（常规 RAG）
```

不强求覆盖率 100%，**让确定性路径优先**：如果 `financial_calc_node` 找不到该科目/期间，再降级到 RAG。

### 5.6 验收

- 拿盐城保安 2023/2024/2025 的资产负债表 + 利润表，问 10 个典型问题：
  - "2024 年货币资金多少？" → 必须返回准确数字 + 引用文档名
  - "2023 到 2025 主营业务收入趋势" → 三年数字 + 同比
  - "2025 年流动比率" → 公式 + 结果 + 两个数字来源
- 这 10 题里 ≥ 8 题走确定性路径而非 LLM 计算。
- 故意问"2026 年货币资金"（数据不存在）→ 明确返回"数据不存在"，不要 LLM 编。

---

## 六、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Textin 按页计费，大批量上传成本不可控 | 成本 | OCR 配置加"启用 Textin 的知识库白名单"，默认不全开 |
| 财务报表"非标"严重（如盐城保安那份表，资产负债 + 利润混排在一张表里） | Phase 3 抽取失败率 | 抽取器输出"识别置信度"，低于阈值时只入库 `raw_table_md`，不入 `FinancialFact`；用户可在 UI 手工纠正 |
| zip 上传保留路径，文件名编码（中文 zip 在 Windows/Mac 上常乱码） | Phase 2 标签错 | 用 `zipfile` 的 `Path` + UTF-8/GBK 双尝试；前端 `webkitdirectory` 路径直接是 UTF-8，更稳 |
| 已有文档没有 path/role 标签 | Phase 2 老数据没法过滤 | 加一个"批量重打标签"管理命令，按文档名 + 用户手填的根目录批量回填 |
| Phase 3 标签依赖 Phase 2 | 顺序耦合 | Phase 2 上线前 Phase 3 可以先做"识别"和"入库"两层（不路由），上线 Phase 2 后再开路由 |

---

## 七、交付节奏

```
Day 1-2 ┃ Phase 1 (Textin OCR)              → 上线测试环境
Day 3-5 ┃ Phase 2 (目录/标签)                → 上线测试环境
Day 6-12┃ Phase 3 (财务结构化 + 计算)         → 上线测试环境
Day 13  ┃ 全链路 e2e:用盐城保安整套材料跑一遍   → 评审
```

Phase 1 / Phase 2 可并行（不同人 / 不同分支）。

---

## 八、后续项（不在本计划范围）

- Textin **失败自动回退本地 OCR**（需要权衡"静默劣化"风险）
- 财务报表 **跨期一致性校验**（资产 = 负债 + 所有者权益是否成立）→ 异常告警
- 目录树 UI（B 路）：folders app + MPTT，文档挂树节点；当前 path_segments 元数据已经为这条路留好迁移空间
- 财务**指标看板**：在应用前端直接画图（基于 `FinancialFact` 表）
- 多文档**主体合并**：同一公司在不同年份/不同文档里的报表自动并表

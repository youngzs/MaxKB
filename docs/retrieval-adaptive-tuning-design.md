# 知识库检索自适应调优 设计文档

> 版本：v0.8
> 状态：**A + B + C 三档全部交付并部署**（A/B 2026-05-21，C 2026-05-22）。下游修复 §十一~§十三（拼接截断 / MMR 误伤 / 分段丢年份）+ §十四 问答性能优化（均 2026-05-22）。
> 创建：2026-05-21
> 触发：2026-05-21 chat-entry「企业概况」漏召回 bug —— 70 段落知识库 `top_n=5` 导致唯一的营业执照段落被征信报告(41段)挤出召回。热修已把 chat-entry 两个 app 的 `top_n` 调到 15，本文档是系统性根治。

---

## 一、背景与问题

### 1.1 现象

chat-entry 知识库问答页，问"企业概况"，营业执照里明明有的字段（注册资本/法定代表人/成立日期/经营范围）答"数据缺失"。

### 1.2 根因（已实测确认）

- 知识库「沛县千岛湿地…」有 **17 文档 / 70 段落**，embedding 正常、段落 active、内容完整。
- chat-entry 检索 `top_n=5` —— 70 段里只取 5 段。
- 征信报告单文档就 41 段、且段落彼此**高度相似**（同一张表的不同行）。"企业概况"类查询下，这 41 段的多个雷同段落 + 章程 5 段把召回前 5 名占满 —— **唯一的营业执照段落（仅 1 段）挤不进去**。

### 1.3 问题本质

两个独立缺陷叠加：

1. **召回量不随库规模缩放** —— `top_n` 是 app 上写死的常量。小库 5 够用，70 段的库就不够，几百段的库更不够。
2. **召回结果无多样性约束** —— 纯按相似度排序，一份内容雷同的大文档会用它的 N 个近似段落霸占整个 top-N，把其他文档里"虽不是最高分但唯一相关"的段落挤掉。这就是"重复度"伤害召回。

---

## 二、目标

检索**运行时自适应**，不需要用户手填参数：

- **A 档**：`top_n` 按所选知识库的段落规模自动缩放 —— 保证大库有足够召回量。
- **B 档**：MMR（Maximal Marginal Relevance）重排 —— 召回结果在"相关性"和"多样性"间平衡，抑制单一文档的雷同段落霸榜。

两者叠加 = "根据知识库内容与重复度自动调整"的落地形态。

### 非目标

- 不做"预先量化知识库重复度指标"（C 档）—— 计算贵，且 MMR 在重排时天然处理冗余，无需单独测量。
- 不改 app 的 `knowledge_setting` 数据结构 —— A/B 档是检索步骤内部行为，对上层透明。
- 不强制用户配置 —— 自适应是默认行为；可配置面板（让高级用户覆盖）列为可选后续项。

---

## 三、现状分析（代码已摸清）

### 3.1 检索入口

`apps/application/chat_pipeline/step/search_dataset_step/impl/base_search_dataset_step.py`
→ `BaseSearchDatasetStep.execute(problem_text, knowledge_id_list, ..., top_n, similarity, search_mode, ...)`

**全平台唯一检索入口** —— 每个 app 的 chat、每个工作流的知识检索节点都走它。`top_n` / `similarity` 由 app 的 `knowledge_setting` 传入。

关键流程（execute 内）：
```
embedding_value = embedding_model.embed_query(problem_text)   # 查询向量
vector = VectorStore.get_embedding_vector()
embedding_list = vector.query(..., top_n, similarity, SearchMode(search_mode))
paragraph_list = self.list_paragraph(embedding_list, vector)
result = [reset_paragraph(p, embedding_list) for p in paragraph_list]
```

### 3.2 向量层

`apps/knowledge/vector/pg_vector.py` → `PGVector.query()` → `EmbeddingSearch / KeywordsSearch / BlendSearch`。

检索 SQL（`apps/knowledge/sql/{embedding,blend}_search.sql`）只 SELECT `paragraph_id, comprehensive_score, similarity` —— **不返回 embedding 向量本身**。

→ **MMR 需要候选段落向量**，方案：候选 `paragraph_id` 拿到后，第二次查 `Embedding` 表补取向量（`Embedding` 模型有 `embedding` 列）。不改检索 SQL，零侵入。

### 3.3 `Embedding` 表

`knowledge.Embedding`，表 `embedding`，字段含 `paragraph_id` / `knowledge_id` / `embedding`（pgvector 向量）/ `is_active`。一个段落可能有多条 embedding 行（分块），检索按 `DISTINCT ON (paragraph_id)` 去重取最佳。

---

## 四、方案 A — top_n 按库规模自适应

### 4.1 缩放规则

在 `execute()` 里，`knowledge_id_list` 解析后、调 `vector.query()` 前，统计这些 KB 的 active embedding 段落数，推导一个"建议下限"：

| KB active 段落数 | 建议 top_n 下限 |
|---|---|
| ≤ 10 | 5 |
| 11 – 50 | 10 |
| 51 – 200 | 15 |
| > 200 | 20 |

### 4.2 关键语义 —— 只升不降

`effective_top_n = max(app 配置的 top_n, 上表推导值)`

- **永远不低于用户配置值** —— 用户显式设了 `top_n=30` 就尊重，不给降。
- 只在大库 + 用户用的是小默认值时，自动抬高。
- 小库即使 top_n 偏大也无害（最多把全部段落返回）。

→ 这条 `max()` 语义保证 A 档"只可能改善召回、不可能损害"，零风险。

### 4.3 实现点

`execute()` 内新增 ~25 行：
```python
para_count = Embedding.objects.filter(
    knowledge_id__in=knowledge_id_list, is_active=True
).values('paragraph_id').distinct().count()
effective_top_n = max(top_n, _recommend_top_n(para_count))
```
`_recommend_top_n` 是纯函数（上表），放本文件或 `common` 工具里。

---

## 五、方案 B — MMR 重排

### 5.1 MMR 算法

从候选池里逐个选段落，每步选使下式最大者：

```
MMR(d) = λ · sim(query, d) − (1−λ) · max_{s∈已选} sim(d, s)
```

- `λ` 越大越偏相关性，越小越偏多样性。**默认 λ = 0.7**（业界常用，偏相关但有效抑冗余）。
- `sim` 用余弦相似度（pgvector 向量已归一，点积即可）。

### 5.2 流程

1. **扩大候选池**：用 `effective_top_n × POOL_FACTOR`（**POOL_FACTOR = 4**）作为 `top_n` 调 `vector.query()`，多召回候选。
2. **补取候选向量**：对候选 `paragraph_id` 批量查 `Embedding` 表取 `embedding` 向量（一个段落多行时取与查询最相似的一条，与检索 SQL 的 `DISTINCT ON` 口径一致）。
3. **MMR 重排**：以 query 向量为锚，从候选池迭代选出 `effective_top_n` 个。
4. 返回 MMR 选中子集，后续 `list_paragraph` / `reset_paragraph` 流程不变。

### 5.3 退化保护

- 候选池 ≤ `effective_top_n` → 跳过 MMR，直接返回（没得重排）。
- 取不到候选向量（异常 / 脏数据）→ 跳过 MMR，回退纯相似度排序。**MMR 失败绝不能让检索整体失败。**
- `directly_return` 命中（`list_paragraph` 里的特判）优先级最高，不进 MMR。

### 5.4 实现点

- 新建 `apps/application/chat_pipeline/step/search_dataset_step/mmr.py` —— 纯函数 `mmr_rerank(query_vec, candidates, k, lambda_)`，无 Django 依赖，可单测。
- `execute()` 内：扩大 `top_n` 调 query → 补向量 → 调 `mmr_rerank` → 截断。新增 ~60 行。

---

## 六、参数与默认值

| 参数 | 默认 | 说明 |
|---|---|---|
| `_recommend_top_n` 阶梯 | 见 §4.1 | hardcode 常量；后续可配化 |
| `POOL_FACTOR` | 4 | 候选池 = effective_top_n×4 |
| MMR `λ` | 0.7 | 相关性/多样性平衡 |
| MMR 开关 | 默认开 | 留一个 env / 常量开关，可一键回退到纯相似度排序 |

→ 全部先 hardcode 在一个 `constants` 区块；可配置 UI 面板列为后续可选项。

---

## 七、影响面与风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| `execute()` 是全平台检索入口，改动影响所有 app + 工作流知识节点 | 高 | A 档 `max()` 语义零损害；B 档全程退化保护 + 总开关；改动集中在一个方法 |
| MMR 改变所有检索结果集（即预期效果，但是行为变更） | 中 | 总开关默认开、可秒回退；上线后用真实库 smoke 对比开/关结果 |
| 补取候选向量 = 每次检索多一条 DB 查询 | 低 | 候选池 ≤ 数十条，按 paragraph_id 批量 IN 查询，`embedding` 列有索引；实测延迟增量预期 <50ms |
| 本测试环境 `manage.py test` 跑不起来（无 pgvector） | 中 | 用 shell smoke：真实库 + 独特 workspace_id 临时数据；MMR 纯函数 `mmr.py` 可脱离 Django 单测 |

---

## 八、实施步骤（建议单独 session 执行）

1. `mmr.py` 纯函数 + 纯函数单测（不依赖 Django，本地可跑）。
2. `_recommend_top_n` 阶梯函数 + 单测。
3. 改 `execute()`：接入 A 档（top_n 自适应）+ B 档（扩召回 → 补向量 → MMR）。
4. 总开关常量。
5. 服务器 shell smoke：对「沛县千岛…」库，关 MMR / 开 MMR 各跑一次"企业概况"检索，对比营业执照段落是否进入结果集。
6. 部署（docker cp + restart）+ chat-entry 实测。
7. 回归：随便挑 2 个已有 app 的对话，确认普通检索没退化。

预估 ~200 行（mmr.py + execute 改动 + 测试）。

---

## 九、验证口径

- **必过**：「沛县千岛…」库问"企业概况"，营业执照段落进入召回，注册资本/法定代表人/成立日期/经营范围都能答出。
- **不退化**：小库（≤10 段）的 app 对话，结果与改动前一致（A 档 max 语义 + 候选池够小时 MMR 自然跳过）。
- **延迟**：单次检索延迟增量 < 100ms。

### 9.1 A 档 + B 档 交付实测（2026-05-21）

「沛县千岛…」库（17 文档 / 70 段落）宽泛查询"完整尽调报告"对比：

| | 召回总段 | 财务段 | 三张财务报表覆盖 |
|---|---|---|---|
| 纯相似度 top_n=20 | 20 | 3（全是资产负债表） | ✗ 利润表/现金流量表未进 |
| **A+B（已部署）** | 20 | 4 | ✅ 利润表/现金流量表/资产负债表 全到 |

A 档生效：70 段库把 chat-entry 配置的 `top_n=15` 自适应抬到 `20`。
B 档生效：MMR 把征信报告 41 个雷同段落压制，利润表/现金流量表挤进 top-20。

→ 2026-05-21 chat-entry 漏召回 bug 已根治。

---

## 十、方案 C —— 查询拆解

> 状态：**已交付并部署、shell smoke 通过**（2026-05-22）。A+B 已修 bug；C 是针对"一次性多 section 报告"场景的**深度覆盖增强**。

### 10.1 为什么还要 C —— 实测依据

A+B 之后，又用查询拆解模拟做了对比（同一宽泛查询，5 个聚焦子查询各检索 + MMR + 合并去重）：

| | 召回总段（去重） | 财务段 | 三张财务报表覆盖 |
|---|---|---|---|
| A+B | 20 | 4 | ✅ 全到（每张表 ~1 段） |
| **C（查询拆解）** | 29 | **9** | ✅ 全到（每张表 ~3 段） |

**结论**：A+B 已让三张报表都进召回（bug 已修）；C 的增量价值是**加深覆盖** ——
财务报表是多段文档（第1/3、第2/3部分…），A+B 每张表约 1 段、C 约 3 段，
分散在后续 part 的细科目数字 C 更全。同时每个 section 都有专属检索，
管理团队/股权结构这类"窄 section"也不会被摊薄。对"生成完整尽调报告"主场景 C 明确更优。

### 10.2 核心问题

宽泛查询（"生成完整尽调报告：概况+股权+管理+征信+财务"）的 embedding 是
5 个意图的"平均向量"，对任何单一意图都不强匹配。实测：同一库同样 top_n，
查询从"宽泛"换成"聚焦财务"，财务段落排名从 #46 跳到 #1。C 把宽问题拆成多个
聚焦子查询，从根上消除"平均向量"稀释。

### 10.3 流程

```
用户问题
  → [LLM 拆解] → 1~N 个聚焦子查询
                  · 简单问题（"注册资本多少"）→ 拆解器原样返回 1 个，等于不拆
                  · 宽泛问题 → 返回 N 个（N ≤ MAX_SUB_QUERIES）
  → 每个子查询：走现有 A+B 检索管线（top_n 自适应 + MMR）
  → 合并：union 所有段落，按 paragraph_id 去重，
          每段取跨子查询最高分，整体 cap 到 MERGE_CAP 段
  → 喂给回答步骤
```

### 10.4 关键设计点

| 点 | 方案 |
|---|---|
| **拆解 LLM 调用** | 用 workspace 的 chat 模型。拆解 prompt 要求模型输出 JSON 数组；解析失败 → 退化为"不拆"（原问题单查询），绝不让拆解失败阻断检索。 |
| **裁判门（是否拆）** | 不另做启发式 —— 让拆解器自己判断：简单问题就返回 `["原问题"]`。一次 LLM 调用兼任"判断 + 拆解"。 |
| **子查询数上限** | `MAX_SUB_QUERIES = 6` —— 防止模型拆过细导致检索次数爆炸。 |
| **合并 cap** | `MERGE_CAP = 30` —— N×top_n 去重后仍可能几十段，cap 到 30 控制 context/token。按"跨子查询最高分"排序后截断。 |
| **落点** | chat pipeline 检索前。两种实现：(a) 新增独立 pipeline step；(b) 在 search 步骤内循环。**实现取 (b)** —— 摸清 pipeline 后发现：(a) 需新增 `i_*` 接口 + `impl` + serializer + `chat.py` 接线，且 *仍要* 改 search step 才能循环；(b) 与 A+B 既有形态一致（A `adaptive_top_n` / B `mmr_filter` 都是 search step 文件里的模块函数，非独立 step），接线为零、风险更低。"调 chat 模型"非阻碍：search step 经 `manage.context['model_id']` 即可拿到 app 对话模型。 |
| **开销** | 每问多一次 LLM 调用 + N 次检索（检索便宜）。简单问题因"裁判门"只多一次拆解调用、不多检索。 |

### 10.5 与 A/B 的关系

C 不替代 A/B —— **三者叠加**：C 拆出的每个子查询，仍走 A 档（top_n 自适应）+ B 档（MMR）的检索管线。C 解决"多意图稀释"，A 解决"召回量"，B 解决"子查询内部冗余"。

### 10.6 实施步骤

1. ✅ 摸清 chat pipeline 的 step 注册与执行顺序（`apps/application/chat_pipeline/`）。
   —— `PipelineManage` 顺序执行 step 列表；search step 是 chat_simple 路径专用，
   workflow 知识检索节点是另一份独立实现（`BaseSearchKnowledgeNode`），C 不影响 workflow。
2. ✅ 拆解 prompt + JSON 解析 + 退化保护 —— `query_split.py`（无 Django 依赖，11 个本地单测全过）。
3. ✅ search step 内多子查询检索 + 合并去重 cap —— `base_search_dataset_step.py`。
4. ✅ 裁判门 —— `parse_sub_queries` 对简单问题/解析失败返回 1 个子查询，
   `execute()` 走单查询路径，与 A+B 行为字节级一致（单测覆盖）。
5. ✅ shell smoke（2026-05-22，千岛库 17 文档 / 70 段落，见下表）。
6. ✅ 部署：`docker cp` 两个文件进容器 `1Panel-maxkb-5IZn` + `docker restart`，服务正常。

**改动文件**：`query_split.py`（新，prompt + 解析纯函数）+
`impl/base_search_dataset_step.py`（`split_query` / `merge_embedding_lists` / `_retrieve_one` 三个
helper + `execute()` 接入 + 常量 + `get_details` 暴露 `sub_query_list`）。约 130 行。

### 10.7 C 档 shell smoke 实测（2026-05-22）

千岛库（workspace=default，拆解模型 `deepseek-ai/DeepSeek-V4-Flash`）：

| 查询 | 拆解结果 | 召回总段 | 财务段 | 三张财务报表 |
|---|---|---|---|---|
| **宽泛**：生成完整尽调报告：企业概况、股权结构、管理团队、征信、财务 | 5 个子查询：企业概况 / 股权结构 / 管理团队 / 征信情况 / 财务数据 | 30（MERGE_CAP 生效）| **9** | ✅ 资产负债表 5 / 现金流量表 3 / 利润表 1 |
| **简单**：注册资本是多少 | 1 个（裁判门 —— 未触发多路检索）| 20（A 档把 top_n=15 抬到 20）| 4 | 资产负债表 2 / 利润表 1 / 现金流量表 1 |

→ 与 §10.1 模拟实测（财务段 9）一致；裁判门按预期工作 —— 简单问题只 1 路检索。
五个 section（概况/股权/管理/征信/财务）全覆盖。**C 档验收通过。**

---

## 十一、召回后上下文拼接截断 —— C 档暴露的下游瓶颈

> 状态：**已修复并部署**（2026-05-22）。

### 11.1 现象

chat-entry 千岛库问「列出企业 2023/2024/2025 三年财务状况：总资产、净资产、收入、利润」，
回答只给出 2023 年利润数据，2024/2025 答「资料中未包含」。

### 11.2 根因（逐环节实测）

**不是检索问题、也不是查询拆解问题。** 实测：知识库里利润表/资产负债表/现金流量表
各有 2023/2024/2025 三个独立文档；C 档正确拆成 3 个年份子查询；A+B 检索 + 合并把
三年共约 30 段财务报表**全部正确召回**（score 0.45~0.58，未被相似度阈值卡掉）。

真正的卡点在召回之后的**上下文拼接**：`generate_human_message_step.to_human_message`
按 `max_paragraph_char_number` 逐段累计拼接，**一旦累计字符超限即 `break`、丢弃后续
全部段落**。该 app 配置 `max_paragraph_char_number=5000`，而 30 段召回内容拼全约
25000 字符 —— 5000 窗口只装得下前 9 段，9 段财务报表里 7 段被丢、没进 LLM。LLM 基于
残缺资料如实回答「未包含」。

两个叠加缺陷：
1. **窗口太小**：`max_paragraph_char_number=5000` 是过时的保守默认，装不下多 section 召回。
2. **拼接顺序非相关性序**：拼接按 `list_paragraph` 的库表顺序，检索/MMR/拆解算出的
   相关性在此处丢失 —— 5000 配额还被征信报告的雷同段落占去不少，财务报表段反被挤出。

**C 档的连带效应**：C 把召回从十几段增加到约 30 段（数据更全，是好事），但下游 5000
窗口不变，于是更多段落在拼接时被丢。C 把瓶颈从「检索召回」转移并暴露到「上下文窗口」。

### 11.3 修复

1. **按相关性排序**（代码，对所有 chat pipeline app 通用）：`to_human_message` 拼接前
   按 `comprehensive_score` 降序排序 —— 命中上限截断时丢弃的是相关性最低的段落。
2. **调大窗口**（配置）：千岛库 app 的 `max_paragraph_char_number` 5000 → 30000
   （Application 本体 + 全部 3 个 ApplicationVersion）。约 26500 字符可全部容纳。

### 11.4 验证（2026-05-22）

修复后实测：execute 召回 29 段 → `to_human_message` 拼接 26499 字符 →
**29 段全部进入 LLM 上下文**，"2023年度/2024年度/2025年度"三年财务数据全部在内；
拼接顺序按 score 降序（0.579→0.480）。

### 11.5 遗留

财务三表 PDF 解析质量差（表头 `利润表|利润表|col5|col6` 噪声多、段落长），属数据治理
问题；长期可重新切分清洗，让单段更短更密、相同窗口容纳更多有效信息。本次未处理。

---

## 十二、MMR 误伤多年同类报表 —— B 档冗余判定缺陷

> 状态：**已修复并部署**（2026-05-22）。

### 12.1 现象

§十一 修复窗口截断后，chat-entry 千岛库问三年财务，2023/2024 能答、**2025 仍缺**，
且总资产/净资产答不出。

### 12.2 根因

把三年三表数据全部 dump 核对 —— **数据完整优质**（营收/净利润/资产总计/所有者权益
三年齐全）。逐环节诊断定位到 **B 档 MMR**：

财务报表 PDF 解析成 markdown 后，每段开头一大坨雷同结构（`资产负债表│资产负债表│
…│col9│col10│---`），这些噪声主导 embedding 向量 → 三年同类报表段落向量高度相似
（cosine 0.95+）。B 档 MMR 的多样性惩罚把它们当冗余互相绞杀。

实测同一查询：**MMR 开财务段召回 4、MMR 关召回 9**。MMR 关时三年利润表 + 三年
资产负债表第2部分（总资产/净资产所在）全部召回。

MMR 初衷（§五）是压制**单文档内**雷同段落霸榜（征信报告 41 段在一个文档里），却
误伤了**跨文档、跨年份**的同类报表 —— 而「多年对比」恰恰需要这些段落全部召回。
召回时好时坏（验证时三年齐、线上只两年）也源于此 —— MMR 绞杀结果每次有浮动。

### 12.3 修复

`mmr_rerank` 的冗余惩罚**只在同 `document_id` 的已选段落间计算，跨文档不惩罚**：
- 同文档雷同段落（征信报告 41 段，同一 document）→ 照常压制，B 档初衷保留。
- 跨文档同类报表（三年利润表 = 3 个独立文档）→ 不再误判为冗余。

`mmr_filter` 从 `Embedding` 表一并补取 `document_id`（本就有该外键，零额外查询）。
纯函数单测覆盖「跨文档雷同保留 / 同文档雷同压制」两条核心路径。

### 12.4 验证（2026-05-22）

修复后实测用户原查询：召回 23 段、财务报表 11 段，三年利润表 + 三年资产负债表
第2部分全部召回；**12 项关键财务数字（三年 ×营收/净利润/资产总计/所有者权益）
全部进入 LLM 上下文**。

---

## 十三、财务报表分段丢失年份 —— LLM 年份归属错乱

> 状态：**已修复（数据层）**（2026-05-22）。

### 13.1 现象

§十一/§十二 修复后，三年财务数据都进了 LLM 上下文，但 LLM 回答时**年份系统性
错位** —— 把 2024 年的总资产/净资产标为 2023 年、2025 标为 2024，"2025"显示缺失。

### 13.2 根因

资产负债表在知识库里按 part 切成 3 段（第1/2/3部分），现金流量表切成 2 段：

- **年份**（`2024-12-31`/`2024年度`）只在**第1部分**段落
- **总资产（资产总计）、净资产（所有者权益合计）** 在**第2部分**段落
- 而第2部分段落 content 里**没有任何年份字样** —— 纯数据行

LLM 拿到三个长得几乎一样、且都不带年份的「资产总计 XXX」段落，无法归属年份 →
张冠李戴。利润表是整张表 1 段（年份与数据同段），故不受影响、答得对。

### 13.3 修复（数据层）

`generate_human_message.to_human_message` 拼接格式为 `{title}:{content}`，title
会进入 LLM 上下文。因此给财务报表所有段落的 **title 补年份前缀**（如
「2024年度资产负债表 (第2/3部分)」），年份从同文档第1部分段落提取。共修订
18 段 title。**content / embedding 不动，零检索风险。**

### 13.4 验证（2026-05-22）

修复后：三年资产负债表第2部分段落 title 各带正确年份，资产总计期末余额
2023≈275M / 2024≈301M / 2025≈355M 与年份一一对应。

### 13.5 遗留 / 根治建议

title 补年份是**数据层临时修复** —— 若该文档被重新上传/重新解析，title 会再次
丢年份。根治应在文档解析/分段环节：多 part 财务报表整表不切分，或每段自带表头
年份。属 MaxKB 文档处理能力范畴，本次未改。

---

## 十四、问答性能优化 —— 对话模型选型

> 状态：**已对比验证，保留 deepseek-reasoner**（2026-05-22）。

### 14.1 现象

A/B/C 全部上线后，chat-entry 问答出结果慢。

### 14.2 耗时构成

单次实测：主 LLM 生成占 ~90%，查询拆解 LLM ~20%，N 路检索仅 ~5%。
**检索（A/B/C 那套）不是瓶颈，瓶颈是 LLM 调用。**

### 14.3 一次被推翻的误判

初次单次采样：deepseek-reasoner 主 LLM 21s、换 DeepSeek-V4-Flash 后测得 6s，
据此判断「reasoner 是推理模型故慢、换 Flash」并切换了对话模型。
**但该结论基于单次采样 —— 随后的系统对比推翻了它。**

### 14.4 模型对比测试

2 个候选模型 × 3 个代表性问题（多年财务对比 / 简单事实 / 征信分析），实测：

| 模型 | 平均合计 | 平均生成 | 波动区间 |
|---|---|---|---|
| **deepseek-reasoner**（deepseek 官方）| **11.6s** | 8.3s | 稳定 4~21s |
| DeepSeek-V4-Flash（siliconCloud）| 30.0s | 25.6s | **剧烈 6~42s** |

Flash 对长输出问题动辄 40s，reasoner 稳定在 10~20s。两模型对「三年财务对比」
都正确列出 2023/2024/2025 全部数据、年份归属无误 —— §十一~§十三 修复确认生效。

### 14.5 根因修正

慢与快**不是「推理 vs 非推理」的差异，而是「服务商供给」的差异**：

- siliconCloud 的 DeepSeek-V4-Flash：长输出时 TPS 极低、响应不稳定（6~42s）。
  （此前 embedding 也在该 provider 上限流过 —— 同一服务商的稳定性问题。）
- deepseek 官方的 deepseek-reasoner：虽是推理模型（带思维链），但官方算力稳定，
  总耗时反而更短、可预期。

→ **已换回 deepseek-reasoner**，app 对话模型 model_id 恢复为
`019e4896-7b4e-7971-97d8-194b056870a5`。

### 14.6 后续可选优化

- 配 deepseek 官方的 `deepseek-chat`（非推理对话版）再纳入对比 —— 官方稳定 +
  省思维链，预期最快。
- 查询拆解加轻量预判跳过简单问题、C 档多路检索并行化、`max_paragraph_char_number`
  适度回调。检索仅占 5%，收益有限。

### 14.7 教训

性能结论必须基于**多次 / 多场景采样** —— LLM 服务波动极大（同一模型 6s~42s），
单次采样会严重误导（§14.3 即是教训）。模型选型要连带评估**服务商供给稳定性**，
不能只看「模型架构」。

---

## 版本记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-05-21 | 设计稿：A 档 top_n 自适应 + B 档 MMR 重排，含代码插入点、参数默认值、风险与实施步骤 | Finance Workspace 小组 |
| v0.2 | 2026-05-22 | A+B 交付并部署（§9.1 实测）；新增 §十 方案 C 查询拆解 —— 含实测依据、流程、关键设计点、实施步骤，待下个 session 完成 | Finance Workspace 小组 |
| v0.3 | 2026-05-22 | C 档代码完成：`query_split.py`（prompt + 解析）+ `base_search_dataset_step.py`（多子查询检索 + 合并去重 cap）；落点定为 (b) search step 内实现（理由见 §10.4）；纯函数本地单测全过。待部署 + shell smoke | Finance Workspace 小组 |
| v0.4 | 2026-05-22 | C 档部署到测试环境（docker cp + restart）并通过 shell smoke（§10.7：宽泛查询拆 5 子查询 / 财务段 9，简单查询裁判门只 1 路）。A+B+C 三档全部上线 | Finance Workspace 小组 |
| v0.5 | 2026-05-22 | 新增 §十一：修复 C 档暴露的「上下文拼接截断」下游瓶颈 —— `to_human_message` 按相关性排序（代码）+ 千岛库 app `max_paragraph_char_number` 5000→30000（配置）。修复后三年财务数据全部进 LLM 上下文 | Finance Workspace 小组 |
| v0.6 | 2026-05-22 | 新增 §十二：修复 B 档 MMR 误伤多年同类报表 —— `mmr_rerank` 冗余惩罚改为只在同 `document_id` 内生效，跨文档不惩罚。修复后用户原查询 12 项关键财务数字全部进 LLM 上下文 | Finance Workspace 小组 |
| v0.7 | 2026-05-22 | 新增 §十三：修复财务报表分段丢失年份致 LLM 年份归属错乱 —— 给 18 段财务报表段落 title 补年份前缀（数据层，content/embedding 不动）。修复后三年总资产与年份一一对应 | Finance Workspace 小组 |
| v0.8 | 2026-05-22 | 新增 §十四：问答性能优化。检索仅占 5%、瓶颈是 LLM。模型对比测试表明 deepseek-reasoner（官方，平均 11.6s）反而比 DeepSeek-V4-Flash（siliconCloud，平均 30s 且波动剧烈 6~42s）更快更稳 —— 保留 reasoner。慢的根因是服务商供给差异而非模型架构；曾基于单次采样误判换 Flash、经对比推翻并换回 | Finance Workspace 小组 |

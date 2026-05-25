# 知识库改进 Phase 4 — UX 提升

> 版本：v0.1
> 状态：**待评审**
> 创建：2026-05-25
> 依赖：[Phase 1/2/3 已交付](knowledge-base-improvements-plan.md)
> 目标：把后端已经具备的能力（标签过滤 / 财务确定性计算）转成用户能直接看到的好体验

## 一、价值排序

| Sub-phase | 用户视角 | 估时 | 依赖 |
|-----------|---------|------|------|
| **4b** 财务问答应用模板 | 应用市场多一个"财务问答 — 盐城保安"模板，admin 点一下复制就能用，不用自己拉节点 | 1 天 | Phase 3 |
| **4a** Chat-entry 运行时标签选择器 | 问答输入框上方一排 chip："只问 [借款人] [反担保人]" / "只看 [财务报表]"，点了再问，召回立刻收敛 | 2-3 天 | Phase 2 |
| **4d** 一致性校验 + 文档列表警告 | 抽取的报表如果不平（资产 ≠ 负债+权益），文档列表显示 ⚠️ tooltip 提示哪里不平 | 1 天 | Phase 3 |
| **4c** 现金流量表科目别名补全 | 经营/投资/筹资活动现金流问答也走确定性路径 | 0.5 天 | Phase 3 |

**推荐顺序**：4b（最快的"哇哦"时刻）→ 4a（最大 UX 提升）→ 4d → 4c

总估时 ~5-6 天。

---

## 二、4b — 财务问答应用模板

### 用户故事

需求方：「我想要一个能问'2024 年货币资金多少'就秒出精确数字、问'公司主营业务'就走 RAG 摘要的应用 —— 不用自己拼工作流」。

### 实现

新增一份 workflow JSON 模板：`apps/application/flow/default_workflow_finance.json`

```
start_node
  ↓
intent_node ("数字查询/对比/比率/总额/同比/环比" vs "其他")
  ├─ 命中数字意图 → parameter_extraction_node (从问题里抽 entity/period/line_item) → financial_calc_node
  └─ 否则 → search_knowledge_node (tag_filter 留空 / 由 admin 后续配置)
  ↓ (两路汇合到)
ai_chat_node
  - system prompt: "如果上一步提供了 financial.data 字段，优先用它的数字作为权威数据回答；
                   否则用 search_knowledge 的 paragraph_list 作答。
                   每条数字都要标注 [来源:文档名]。"
```

### 落点

- `apps/application/flow/default_workflow_finance.json`（新）
- `apps/application/serializers/application.py`：应用创建对话框新增"从模板创建 → 财务问答"选项
- 前端：`ui/src/views/application/components/AddApplicationDialog.vue`（或类似）增加模板选择 chip

### 验收

- 创建"财务问答 — 盐城保安"应用 → 不需要任何手工拉节点 → 问"2024 年净利润多少"→ 走 financial_calc → 返回带引用的精确数字
- 问"公司主营业务范围" → 走 RAG → 返回带文档引用的摘要

---

## 三、4a — Chat-entry 运行时标签选择器

### 用户故事

需求方：「我每次问问题前，能不能选'只在借款人的征信报告里找'？我现在的 app 既绑了借款人又绑了反担保人的资料，模型经常串题」。

### 实现

#### 前端

- `ui/src/views/chat-entry/index.vue` 输入框上方加 tag picker：
  - 进入页面时 → 调 `getTags(knowledge_id)`（已存在 API）拉知识库标签 → 按 key 分组（path / role / doc_type）
  - 用户选了 → 存到 chat-entry 的本地 state（不污染 store）
  - 提交 message 时把 `runtime_tag_filter: [{key,value},...]` 放进 chat 请求 body

- UI 风格：
  - 默认折叠成一行"+ 标签筛选"
  - 展开显示分组多选 chip
  - 选了之后输入框上方显示已选 chip + ✕ 一键清空

#### 后端

- `apps/chat/serializers/chat.py`（chat message 接收处）接受 `runtime_tag_filter` 字段
- `apps/application/chat_pipeline/...` 或 `workflow_manage` 把它注入到 workflow params
- `ISearchKnowledgeStepNode._run` 优先用 runtime 的 `tag_filter`、否则用编辑器配置的（合并策略：runtime AND 编辑器）

#### 难点

一个 workflow 里可能有**多个** `search_knowledge_node`（例如 finance template 的"数字路径"和"RAG 路径"都用到知识库）。MVP 行为：**全部应用 runtime tag_filter**（最朴素 / 最不会让用户迷惑）。后续版本可在节点配置里加"是否响应运行时标签"开关。

### 落点

| 文件 | 改动 |
|------|------|
| `ui/src/views/chat-entry/index.vue` | 输入框上方 tag picker 组件 |
| `ui/src/components/ai-chat/index.vue` | 透传 runtime_tag_filter 到 chat API |
| `ui/src/api/application/application.ts` | message 请求 schema 加 runtime_tag_filter |
| `apps/chat/serializers/chat.py` | 接收字段并写入 workflow params |
| `apps/application/chat_pipeline/...` 或 workflow_manage | 注入 runtime context |
| `apps/application/flow/step_node/search_knowledge_node/i_search_knowledge_node.py` | execute 里合并 runtime + 编辑器 tag_filter |

### 验收

- 千岛库应用：进入 chat-entry → 看到 chip "[借款人]、[反担保人]、[财务报表]、[征信报告]" 可选
- 选 "[借款人] + [财务报表]" → 问"主营业务收入" → 召回段落全部来自借款人目录下的财务报表
- 不选任何 chip → 行为与现在完全一致

---

## 四、4d — 一致性校验 + 文档列表警告

### 用户故事

需求方：「抽取出来的报表万一抽错了我怎么知道？最好系统能自己看出'这张报表不平'然后告诉我」。

### 实现

#### 校验规则（资产负债表）

抽完后跑：
- `资产总计 ≈ 负债合计 + 所有者权益合计`（容差 1%）
- `流动资产合计 + 非流动资产合计 ≈ 资产总计`（如有这两个合计）

#### 校验规则（利润表）

- `营业利润 ≈ 营业收入 - 营业成本 - 营业税金及附加 - 各项费用`
- `利润总额 ≈ 营业利润 + 营业外收入 - 营业外支出`
- `净利润 ≈ 利润总额 - 所得税费用`

#### 数据落点

- `FinancialStatement` 模型加 `meta = JSONField`（migration `0010_financial_statement_meta`）
- 不平衡时把 warning 列表写进 `statement.meta['warnings']`：
  ```json
  [{"type": "balance_mismatch", "expected": 481682943, "actual": 478000000, "diff_pct": 0.77, "details": "资产总计 vs 负债+权益"}]
  ```

#### 前端

- `ui/src/views/document/index.vue`：文档列表"状态"列旁加一个 ⚠️ 图标（当文档有任何 FinancialStatement.meta.warnings）
- hover 显示 tooltip：列出每条 warning
- 点击 → drawer 显示原始 markdown 表 + 抽取出的 facts + warnings 详情

### 落点

| 文件 | 改动 |
|------|------|
| `apps/knowledge/models/financial.py` | `FinancialStatement.meta` 新增字段 |
| `apps/knowledge/migrations/0010_*.py` | 新 migration |
| `apps/knowledge/services/financial_consistency.py`（新） | check_balance / check_income 函数 |
| `apps/knowledge/services/financial_auto_extract.py` | 抽取后调一次 consistency check |
| `apps/knowledge/views/document.py` 或新 `financial_statement.py` | GET `/document/<id>/financial_statements` 返回报表 + warnings |
| `ui/src/views/document/index.vue` | 警告图标 + tooltip |
| `ui/src/views/document/FinancialStatementDrawer.vue`（新） | 详情抽屉 |

### 验收

- 上传一份"做手脚的"资产负债表（手工把某个值改掉，让资产 ≠ 负债+权益）→ 文档列表能看到 ⚠️
- hover 显示"资产总计 1,109,534,487 vs 负债+权益 1,109,534,491 = 差额 0.0%（容差内）"
- 故意改大差额 → "差额 5.2%（超阈值）"

---

## 五、4c — 现金流量表科目别名补全

### 用户故事

需求方：「为什么经营活动现金流的问题走 RAG 而不是确定性计算？」

### 实现

补 `_LINE_ITEM_ALIASES` 表里的现金流量科目，例如：

```python
'销售商品、提供劳务收到的现金': '销售商品收到的现金',
'购买商品、接受劳务支付的现金': '购买商品支付的现金',
'经营活动现金流入小计': '经营活动现金流入小计',
'经营活动现金流出小计': '经营活动现金流出小计',
'经营活动产生的现金流量净额': '经营活动现金流量净额',
'投资活动现金流入小计': '投资活动现金流入小计',
'投资活动产生的现金流量净额': '投资活动现金流量净额',
'筹资活动现金流入小计': '筹资活动现金流入小计',
'筹资活动产生的现金流量净额': '筹资活动现金流量净额',
'现金及现金等价物净增加额': '现金及现金等价物净增加额',
'期末现金及现金等价物余额': '期末现金及现金等价物余额',
...
```

加完用真实现金流量表回归测试。

### 验收

- 上传一份现金流量表 → 抽取出 statement_type='cash_flow' 的 FinancialStatement
- 问"2024 年经营活动现金流量净额" → 走 financial_calc_node 返回精确数字

---

## 六、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 4b 模板里的 intent_node 关键词集合不全 | 数字问题被错路由到 RAG | 模板的 intent_node 给两个分支都允许 fallback：RAG 答不全时 LLM 可以触发"重试用 financial_calc" |
| 4a 多个 search_knowledge_node 时的标签策略不确定 | 用户体验混乱 | MVP 全部应用；后续节点配置加开关 |
| 4d 校验阈值太严会误报 | 用户疲劳 | 阈值（1% / 5%）做成系统设置，admin 可调 |
| 4c 别名表越补越乱 | 维护成本 | 限定只补"中国会计准则"标准科目；其他特殊行业（金融/保险）后续单独维护 |

---

## 七、与 Phase 1-3 的关系

Phase 4 的所有功能都是**叠加在已交付的后端能力之上**：

- 4a / 4b 用 Phase 2 的 `tag_filter` + Phase 3 的 `financial_calc_node`
- 4d / 4c 复用 Phase 3 的 extractor 框架

不需要回头改 Phase 1-3 的代码，只是加新 UI / 新规则 / 新模板。

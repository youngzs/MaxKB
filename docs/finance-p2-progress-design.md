# 融资工作台 P2 — 进度归集 设计文档

> 版本：v0.7（**MVP 达成** — Gate 0-4 完成；剩 Gate 5 fast-follow）
> 状态：**Gate 4 完成 = P2 MVP 闭环** — `progress/dashboard` 聚合端点 + 运行时风险评分（停留时长/临期/材料失败）+ 进度页 KPI 卡条 + Gantt 阶段块风险标全部落地并部署。
> 上游：本文档是 [finance-module-design.md](finance-module-design.md) §1.2 第 5 项「进度归集」的落地设计，承接 P0/P1（Gate 1-8 已交付）。
> 创建：2026-05-18 ｜ Gate 0 评审通过：2026-05-18 ｜ Gate 1-4 交付：2026-05-20

---

## 一、背景与目标

### 1.1 业务背景

P0/P1 已交付融资项目库、材料整理、流程文档、审核发送闭环。但**项目进度本身仍散落**：

- 项目状态只有扁平 5 态（筹备/材料准备/对接中/已落地/已终止），看不到"卡在哪一步、卡了多久"。
- 没有责任人、没有计划/实际时间，无法回答"这个项目该完成的节点完成了没"。
- 高管想看「当前在途融资全景」，仍要业务员临时拉 Excel。
- 阶段停滞、材料缺口、临近 deadline 这些异常，靠人盯，等月报才发现。

### 1.2 目标

把跨部门、跨机构、跨数月的融资项目时间线集中到一张看板：

1. **项目时间线**：每个项目按阶段展开的 Gantt 视图，含计划/实际时间、责任人。
2. **风险自动识别**：阶段停留时长、材料完整度、临近 deadline → 自动黄/红标。
3. **高管驾驶舱**：在途总额、平均周期、通过率、机构占比，可下钻。
4. **到期提醒**：关键节点临期，自动通知责任人。

### 1.3 非目标（本期明确不做）

- 不接管对外披露的正式进度报表（只服务内部）。
- 不强制业务员事事填报 —— 阶段流转尽量由系统侧动作自动触发。
- 不做跨 workspace 的集团合并视图（多租户隔离不破）。

---

## 二、需求确认

### 2.1 功能清单（与 i18n `planningDoc.progress` 对齐）

| # | 功能 | P2 范围 | 说明 |
|---|---|---|---|
| F1 | 阶段模型 | ✅ 核心 | 按 `project_type` 定义子阶段模板 |
| F2 | 项目时间线 Gantt | ✅ 核心 | 多项目纵向排列，阶段色块 |
| F3 | 计划 vs 实际时间 | ✅ 核心 | 每阶段 `planned_at` / `actual_at` |
| F4 | 责任人 | ✅ | 见 DR-P2-03 决定粒度 |
| F5 | 风险自动标记 | ✅ | 停留超时 / 材料缺口 / 临期 |
| F6 | 高管驾驶舱 | ✅ | KPI 卡 + 下钻 |
| F7 | 到期提醒推送 | ⚠️ 视 Gate 排期 | 优先站内，邮件/企微后续 |
| F8 | 多对手方并行进度 | ❓ 待定 | 见 DR-P2-02 |

### 2.2 数据来源盘点

| 数据 | 现状 | P2 需要 |
|---|---|---|
| 项目基本信息 | ✅ `FinanceProject` | 复用 |
| 项目状态 | ✅ 扁平 5 态 | 需细化为阶段（见 DR-P2-01） |
| 材料任务 | ✅ `MaterialsTask` | 复用 — 材料完整度信号来自这里 |
| 文档生成 | ✅ `DocumentGeneration` | 复用 — 关键文件信号 |
| 阶段时间 | ❌ 无 | **新建** `ProjectStageRecord` |
| 责任人 | ❌ 只有 `created_by` | **新增字段** |
| 计划时间 | ❌ 无 | 见 DR-P2-04 来源 |
| 对手方 | ❌ 无实体 | 见 DR-P2-02 |

---

## 三、关键设计决策（DR）

> ✅ 以下 4 条已于 2026-05-18 Gate 0 评审**全部按推荐方案确认**。

### DR-P2-01：阶段模型粒度 — ✅ 已确认（中档）

- **✅ 已确认：按 `project_type` 加固定子阶段模板（中档）**
  - 每个项目类型 hardcode 一套有序子阶段（见 §四）。`FinanceProject` 保留现有 5 态 `status` 作为「大状态」（向后兼容、不破 P0/P1），新增 `current_stage_key` 指向类型模板里的细阶段。
  - 理由：扁平 5 态 Gantt 画不出业务细节；可配模板表（StageTemplate）要多 3-4 个 Gate、UI 复杂度陡增，对一个测试/演示环境性价比低。固定模板是甜点 —— 业务语义清晰、改动可控。
- 备选 A（轻）：保持扁平 5 态。Gantt 只画 5 段色块。
- 备选 B（重）：新建 `StageTemplate` 表 + workspace 可配 UI。

### DR-P2-02：多对手方 — ✅ 已确认（free-text 字段）

- **✅ 已确认：本期只在 `FinanceProject` 加 `counterparty` free-text 字段**
  - 记录「主要对手方」（如"中信银行"），不拆独立实体、不支持一项目并跑 N 家。
  - 理由：拆 `ProjectCounterparty` 表会让数据模型复杂度 +50%，Gantt / Dashboard 都要按对手方分 tab。在真实需求验证前先用轻量字段顶住；真要并跑多家，下个 Phase 再追加 DR 升级。
- 备选 A：完全不加。需要跟多家时用户手动复制项目。
- 备选 B：新建 `ProjectCounterparty`（项目 × 机构），每条独立阶段/时间。

### DR-P2-03：责任人粒度 — ✅ 已确认（双层 owner）

- **✅ 已确认：项目级单 owner + 阶段级可选 owner**
  - `FinanceProject` 加 `owner_id`（指向 `sys_user`，默认 = `created_by`）。`ProjectStageRecord` 也带可空 `owner_id` —— 不填则继承项目 owner。
  - 理由：到期提醒需要明确"通知谁"。项目级 owner 兜底，阶段级 owner 覆盖（如尽调阶段归 A、放款阶段归 B），既灵活又不强制。
- 备选 A：只项目级单 owner。
- 备选 B：只阶段级 owner，无项目级。

### DR-P2-04：计划时间来源 — ✅ 已确认（手填）

- **✅ 已确认：项目创建/编辑时业务手填**
  - 创项目表单加一组 `planned_at` 输入（按类型模板列出各阶段，一次填到位，可留空）。
  - 理由：成本最低、控制力最高、demo 即可见效。AI 推荐（取同类型历史均值）依赖样本量，测试环境样本稀疏；CSV 导入是 PMO 已有外部表场景，本期无此前置。
- 备选 A：AI 看同类型历史项目阶段均值推荐。
- 备选 B：外部表 CSV/xlsx 导入端点。

---

## 四、阶段模型（核心交付物）— ✅ 已确认

> 基于 DR-P2-01。每个 `project_type` 一套有序子阶段，`key` 为稳定标识（不可改），`label` 可 i18n。`maps_to_status` 标注该子阶段对应现有哪个大状态（保证 P0/P1 兼容）。
> **2026-05-18 Gate 0 评审：五套模板的子阶段名称与顺序业务方确认无误。**

### 4.1 bank_loan（银行贷款）

| 顺序 | stage_key | 阶段名 | maps_to_status |
|---|---|---|---|
| 1 | `intake` | 立项受理 | preparing |
| 2 | `due_diligence` | 尽职调查 | materials |
| 3 | `materials_prep` | 授信材料准备 | materials |
| 4 | `credit_committee` | 审贷会 | engaging |
| 5 | `approval` | 批复 | engaging |
| 6 | `disbursement` | 放款 | landed |
| 7 | `post_loan` | 贷后管理 | landed |

### 4.2 bond（债券）

| 顺序 | stage_key | 阶段名 | maps_to_status |
|---|---|---|---|
| 1 | `intake` | 立项受理 | preparing |
| 2 | `due_diligence` | 尽职调查与申报材料 | materials |
| 3 | `regulatory_filing` | 监管申报/注册 | engaging |
| 4 | `issuance_prep` | 发行准备 | engaging |
| 5 | `bookbuilding` | 簿记发行 | engaging |
| 6 | `listing` | 上市/登记 | landed |
| 7 | `duration_mgmt` | 存续期管理 | landed |

### 4.3 trust（信托）

| 顺序 | stage_key | 阶段名 | maps_to_status |
|---|---|---|---|
| 1 | `intake` | 立项受理 | preparing |
| 2 | `due_diligence` | 尽职调查 | materials |
| 3 | `risk_approval` | 风控审批 | engaging |
| 4 | `plan_setup` | 计划设立 | engaging |
| 5 | `fundraising` | 募集 | engaging |
| 6 | `established` | 成立 | landed |
| 7 | `duration_mgmt` | 存续期管理 | landed |

### 4.4 abs（ABS）

| 顺序 | stage_key | 阶段名 | maps_to_status |
|---|---|---|---|
| 1 | `intake` | 立项受理 | preparing |
| 2 | `asset_screening` | 基础资产筛选与尽调 | materials |
| 3 | `structuring` | 交易结构设计 | engaging |
| 4 | `rating_filing` | 评级与申报 | engaging |
| 5 | `issuance` | 发行 | engaging |
| 6 | `listing` | 挂牌 | landed |
| 7 | `duration_mgmt` | 存续期管理 | landed |

### 4.5 other（其他）

| 顺序 | stage_key | 阶段名 | maps_to_status |
|---|---|---|---|
| 1 | `intake` | 立项 | preparing |
| 2 | `preparation` | 准备 | materials |
| 3 | `execution` | 推进 | engaging |
| 4 | `landed` | 落地 | landed |
| 5 | `follow_up` | 后续管理 | landed |

> 终止态 `terminated` 是横切状态 —— 任何阶段都可被标记终止，不在子阶段序列里。

### 4.6 阶段流转规则

- 默认按顺序前进（`current_stage_key` 只能进到「下一个」或停在原地）。
- 允许**回退**（材料被打回）—— 但回退要记 `ProjectStageRecord` 一条新记录，审计留痕。
- 不允许跳跃式跨多个阶段（防止数据失真）。如需跳，先逐级流转。
- 大状态 `status` 由 `current_stage_key` 的 `maps_to_status` 自动派生，**不再单独让用户改** —— 消除两套状态打架。

---

## 五、数据模型增量

### 5.1 `FinanceProject` 新增字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `owner_id` | UUID, null | 项目负责人（DR-P2-03）；迁移时回填 = `created_by` |
| `counterparty` | varchar(200), blank | 主要对手方机构名（DR-P2-02） |
| `current_stage_key` | varchar(32), blank | 当前子阶段 key；迁移时按 `status` 反查模板回填 |

### 5.2 新建 `ProjectStageRecord`（阶段记录表）

每个项目 × 每个子阶段一行。项目创建时按类型模板**预生成全部阶段行**（planned_at 可空，actual_at 全空）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | uuid7 |
| `workspace_id` | varchar(64), index | 多租户 |
| `project_id` | UUID, index | 所属项目 |
| `stage_key` | varchar(32) | 子阶段 key |
| `stage_order` | int | 顺序号（冗余，便于排序） |
| `planned_at` | datetime, null | 计划完成时间（DR-P2-04 手填） |
| `actual_at` | datetime, null | 实际完成时间（阶段流转时系统写入） |
| `owner_id` | UUID, null | 阶段责任人；空则继承项目 owner |
| `entered_at` | datetime, null | 进入本阶段的时间（算停留时长用） |
| `status` | varchar(16) | `pending` / `active` / `done` / `skipped` |
| `note` | text, blank | 备注（回退原因等） |
| `created_at` / `updated_at` | datetime | |

索引：`(workspace_id, project_id, stage_order)`、`(status)`。

### 5.3 风险标记 — 不落表，运行时计算

风险标（黄/红）不持久化 —— 由 §七 规则在查询时实时算，避免状态同步问题。若后续要做提醒去重，再单建 `RiskAlert` 表。

---

## 六、API 设计预览

前缀 `/api/finance/`，全部带 `workspace_id` 路径段。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/workspace/<wid>/progress/gantt` | Gantt 数据：项目列表 + 各项目阶段记录，支持 `status` / `owner_id` / `project_type` 过滤 |
| GET | `/workspace/<wid>/progress/dashboard` | 驾驶舱聚合：在途总额、平均周期、通过率、机构占比、风险计数 |
| GET | `/workspace/<wid>/project/<pk>/stages` | 单项目全部阶段记录 |
| POST | `/workspace/<wid>/project/<pk>/advance` | 推进到下一阶段（写 actual_at + entered_at，派生 status） |
| POST | `/workspace/<wid>/project/<pk>/rollback` | 回退一阶段（留痕） |
| PUT | `/workspace/<wid>/project/<pk>/stages/<stage_key>` | 改单阶段 planned_at / owner_id / note |
| GET | `/workspace/<wid>/progress/alerts` | 当前风险项列表（运行时算） |

权限：读用 `FINANCE:READ`，推进/回退/改阶段用 `FINANCE:EDIT`。

---

## 七、风险评分规则

运行时对每个 `active` 阶段算，输出 `none / yellow / red`：

| 信号 | 黄 | 红 |
|---|---|---|
| **阶段停留时长** | `now - entered_at` > 计划时长 ×1.0 | > 计划时长 ×1.5 |
| **临近 deadline** | 距 `planned_at` ≤ 3 天 | 已过 `planned_at` 未完成 |
| **材料完整度** | 关联材料任务有 ≥1 个 `required` 项无匹配文档 | 关联材料任务处于 `failed` |
| **关键文件缺失** | 阶段要求的流程文档未生成 | — |

- "计划时长"= 该阶段 `planned_at` − 上一阶段 `actual_at`（缺数据则跳过此信号）。
- 阈值默认值如上，**Gate 1 先 hardcode**，可配化留待后续。
- 项目级风险 = 其所有 active 阶段风险的最高级。

---

## 八、前端页面规划

路由 `/finance/progress`（菜单已占位，当前渲染 PlanningDoc）。改为实际页面：

- **顶部**：KPI 卡条（驾驶舱核心指标，复用 overview KPI 卡样式）。
- **主体**：Gantt 时间线 —— 纵轴项目、横轴时间，阶段色块；hover 显示责任人 + planned/actual + 风险标。
- **筛选**：项目类型 / 状态 / 责任人 / 风险等级。
- **右侧抽屉**：点项目展开单项目阶段详情，可推进/回退/改计划时间。
- Gantt 选型：复用前端已有 `@logicflow` 不合适（那是流程图）；建议轻量自绘 div 时间条，或引入 `vis-timeline`（评估包体积）。

---

## 九、实施路线（建议 Gate 划分）

| Gate | 范围 | 交付 |
|---|---|---|
| **Gate 0** | 本文档 | 需求确认 + 阶段模型 + DR 评审 ✅ |
| **Gate 1** | 数据底座 | `ProjectStageRecord` 模型 + 迁移（回填存量项目）+ 阶段模板常量 + 项目字段扩展 ✅ |
| **Gate 2** | 阶段流转 API | advance / rollback / 改阶段端点 + 创项目时预生成阶段行 + 计划时间手填表单 ✅ |
| **Gate 3** | Gantt 页面 | `/finance/progress` 时间线视图 + 筛选 + 单项目抽屉 ✅ |
| **Gate 4** | 驾驶舱 + 风险 | dashboard 聚合端点 + 风险评分 + KPI 卡 + 风险标渲染 ✅（= MVP 达成） |
| **Gate 5** | 到期提醒 | alerts 端点 + 站内通知（邮件/企微视情况）← 当前（fast-follow） |

> **MVP 口径（2026-05-18 Gate 0 确认）= Gate 4** —— Gantt + 驾驶舱 + 风险自动标记，
> 才是完整的"进度归集"价值闭环（高管一屏看全 + 异常自动浮现）。
> **Gate 5（到期主动推送）列为 MVP 之后的 fast-follow**，可干净切分、不影响核心闭环。

---

## 十、风险登记

| 风险 | 可能性 | 影响 | 缓解 |
|---|---|---|---|
| 存量项目迁移时 `current_stage_key` 回填不准 | 中 | 中 | 按 `status` → `maps_to_status` 反查取该状态下第一个子阶段；迁移脚本打日志，允许业务事后手工校正 |
| 阶段模板 hardcode，业务想改顺序 | 中 | 中 | Gate 0 评审务必让业务确认 §四 五套模板；改模板 = 改常量 + 迁移，不是热配置 |
| Gantt 前端组件选型踩坑（包体积/交互） | 中 | 中 | Gate 3 先做技术 POC：自绘 div vs vis-timeline，二选一 |
| 风险阈值 hardcode 不符合实际业务节奏 | 高 | 低 | Gate 1 集中放一个 constants 文件；上线后按反馈调；可配化是后续项 |

---

## 十一、Gate 0 待决清单 — ✅ 全部确认（2026-05-18）

1. ☑ **DR-P2-01** 阶段粒度 —— 走「中档：固定子阶段模板」。
2. ☑ **DR-P2-02** 多对手方 —— 本期只加 `counterparty` free-text 字段。
3. ☑ **DR-P2-03** 责任人 —— 「项目级 owner + 阶段级可选 owner」。
4. ☑ **DR-P2-04** 计划时间 —— 「创建项目时业务手填」。
5. ☑ **§四 五套阶段模板** —— 子阶段名称与顺序确认无误。
6. ☑ **§七 风险阈值** —— 默认倍数（×1.0 / ×1.5）、临期天数（3 天）合理。
7. ☑ **§九 Gate 划分** —— MVP 口径定 **Gate 4**；Gate 5 列 fast-follow。

**→ Gate 0 完成，进入 Gate 1（数据底座）。**

---

## 版本记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-05-18 | Gate 0 设计稿：需求确认 + 五套阶段模型 + 4 条 DR + 数据模型 + API 预览 + 5-Gate 路线 | Finance Workspace 小组 |
| v0.2 | 2026-05-18 | Gate 0 评审通过：DR-P2-01~04 按推荐方案确认；五套阶段模板确认；MVP 口径定 Gate 4 | Finance Workspace 小组 |
| v0.3 | 2026-05-20 | Gate 1 数据底座交付：阶段模板常量（`constants/stage_templates.py`）、`ProjectStageRecord` 模型、迁移 0009（建表 + `FinanceProject` 三字段 + 回填存量项目）、Output serializer、单测 | Finance Workspace 小组 |
| v0.4 | 2026-05-20 | Gate 2 后端交付：阶段流转服务（`service/stage_progression.py`）、4 端点（GET stages / PUT 改阶段 / advance / rollback）、创项目预生成阶段行、项目 PUT 收口 status 派生、单测。回退采「就地改 + FinanceAuditLog 留痕」（评审确认）。剩前端计划时间手填表单 | Finance Workspace 小组 |
| v0.5 | 2026-05-20 | Gate 2 完成：补 `GET stage-templates` 端点；前端创建/编辑项目弹窗加「主要对手方」「项目负责人」字段 + 「阶段计划完成时间」手填分组（仅创建态、按类型模板列阶段），编辑态 status 下拉禁用；i18n 三语补键。全部部署测试环境 | Finance Workspace 小组 |
| v0.6 | 2026-05-20 | Gate 3 完成：`progress/gantt` 聚合端点；`/finance/progress` 页面替换 PlanningDoc 占位 —— 自绘 div 时间轴（Gantt 选型 POC 结论：不引入新依赖）、类型/状态/负责人筛选、单项目右抽屉（推进/回退/逐阶段改 planned_at/owner/note）；路由解除 disabled；i18n 三语加 progressPage 段。全部部署测试环境 | Finance Workspace 小组 |
| v0.7 | 2026-05-20 | **Gate 4 完成 = MVP 达成**：`progress/dashboard` 聚合端点（在途总额/平均周期/通过率/机构占比/风险计数）；运行时风险评分 `service/risk.py`（信号 1 停留时长 + 2 临期 + 3 材料 failed；信号 4 关键文件缺失暂缓——缺阶段→文档映射）；阈值常量 `constants/risk_rules.py`；进度页顶部 KPI 卡条 + Gantt 阶段块风险标（黄/红）+ 风险原因 tooltip；单测 `test_risk.py`。全部部署测试环境 | Finance Workspace 小组 |

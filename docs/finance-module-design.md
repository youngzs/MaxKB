# 融资工作台模块设计文档

> 版本：v0.1（Gate 1 设计稿）
> 状态：进行中 — 当前 Gate 1
> 最后更新：2026-05-13

---

## 一、背景与目标

### 1.1 业务背景

国企融资部门日常工作中涉及大量与金融机构（银行、信托、券商、租赁公司、政府引导基金等）的对接、内外部材料准备、内部流程文档撰写、进度跟踪、合规判断等场景。当前痛点主要集中在：

- **信息分散**：政策、利率、机构动态分散于网页、邮件、群聊，缺乏统一入口
- **材料重复劳动**：每次申请几乎都要重新组装公司资质材料包，且容易出现版本不一致
- **流程文档撰写门槛高**：可研报告、董事会决议、立项报告等格式严谨、章节固定，新人上手慢
- **进度难追溯**：一个融资项目跨越数月、涉及多方，节点缺乏中心化看板
- **合规风险**：敏感财务、股权信息在分发过程中无密级控制，存在外泄风险

本模块旨在构建一个基于 MaxKB 平台（知识库 + 工作流 + MCP）的"融资部智能体"，分期落地 5 项核心能力，将上述痛点逐步收口到一个统一工作台。

### 1.2 业务功能蓝图（5 项）

| 功能 | 核心价值 | 难度 | 优先级 | 主要依赖 |
| --- | --- | --- | --- | --- |
| 实时资讯推送 | 主动捕获政策/利率/机构动态并定向推送给关注的项目负责人 | ⭐⭐⭐⭐ 高 | P3 | 外部数据源 / `trigger` / `application/flow` |
| 可行性初判 | 给定项目要素自动出"宜/不宜/补材料"初判建议，并附依据 | ⭐⭐⭐⭐ 高 | P2 | 多模型推理 / 知识库分级 / `application/flow` |
| 融资材料整理 | 按"申请方—申请类型—金融机构"三因素自动拼装完整材料包并发送 | ⭐⭐⭐ 中 | P1 | `knowledge` / `tools` / SMTP / docx 渲染 |
| 进度归集整理 | 跨项目时间线视图，节点状态、负责人、关键文档一屏呈现 | ⭐⭐ 低-中 | P2 | `apps/finance` 本模块表 |
| 流程文档 | 立项报告、可研、决议、合同等公文一键生成（含 AI 占位符） | ⭐⭐⭐ 中 | P1 | docxtpl / `application/flow` / 知识库 |

### 1.3 落地节奏

首期落地 **P1（材料整理 + 流程文档）**，原因：

1. **依赖最少**：两个 P1 不依赖外部数据源接入，闭环最小
2. **价值最显**：材料整理 + 公文撰写是融资部门最耗时也最容易标准化的两个动作
3. **能反向倒逼知识库分级建设**：材料分发必然涉及敏感等级，会拉动 `knowledge` 模块新增 `sensitivity_level` 字段，并产出一批分级清晰的高质量素材，为 P2/P3 打下基础

P2（可行性初判 / 进度归集）与 P3（实时资讯推送）在系统中以 **禁用菜单项占位**（灰色 + "敬请期待" tooltip），告知用户路线图存在但暂未开放。

---

## 二、关键设计决策

以下决策记录（DR, Decision Record）在 Gate 1 启动会议中达成共识，后续 Gate 若需推翻须在本文档追加 DR-XX 并标注超越关系。

- **DR-01：菜单形态** — 选择"左侧菜单"（仿 `/system` 的二级布局），不使用顶部下拉。
  - 理由：国内 B 端项目主流形态；融资工作台子项预计 9+，顶部下拉信息密度低、寻路成本高；与 `apps/system_manage` 现有左侧菜单交互一致，用户心智零迁移成本。

- **DR-02：业务实体存储** — 在 `apps/finance/` 下独立建表，**不复用** `apps/application` 或 `apps/folders` 已有模型。
  - 理由：融资项目业务字段差异大（金额、币种、状态机、对手方、阶段、风险等级），强行复用 `Application` 或 `Folder` 会向通用模型注入业务字段，污染其他模块。独立建表 + 必要时通过外键引用知识库文档，是更干净的边界。

- **DR-03：多租户** — 所有融资表带 `workspace_id`，复用现有 `WorkspaceUserResourcePermission` 鉴权。
  - 理由：与平台其他模块（`knowledge` / `application` / `tools`）一致；天然支持同一套系统服务多个公司/集团子公司；避免重复实现多租户层。

- **DR-04：文档敏感等级** — 给 `knowledge.Document` 增加 `sensitivity_level` 字段，取值 `public / internal / confidential / secret`，默认 `internal`；同时 tag 体系保留作为筛选维度。
  - 理由：发送/打包动作涉及对外披露，单靠 tag 是软约束、可被绕过。`sensitivity_level` 作为硬字段，由后端在打包/发送前做白名单校验。tag 体系不删除，作为业务侧的细粒度筛选（如 "2024Q3"、"上市辅导期"）。

- **DR-05：docx 渲染** — 选用 `docxtpl`（基于 Jinja2 语法）作为 Word 公文模板引擎。
  - 理由：业务方现有公文模板均为 docx 格式；`docxtpl` 支持在 Word 中直接编辑模板（保留样式、表格、页眉页脚），落地成本远低于 `python-docx` 纯代码方式；Jinja 语法学习曲线对模板编辑者友好。

- **DR-06：AI 编排归属** — 业务表只存 `workflow_run_id` 等弱关联字段，AI 编排逻辑下放到 `apps/application/flow/` 现有工作流引擎，**不在 finance 模块内重新实现编排**。
  - 理由：MaxKB 已有完整工作流引擎（`workflow_manage.py` + `step_node/`），重复实现会陷入维护双份引擎的泥潭。融资模块的 AI 能力（生成可研章节、抽取关键要素等）以"预置工作流"形式登记，业务层只负责触发并接收结果。

---

## 三、信息架构与菜单

### 3.1 菜单层级

```
顶部主导航
├── 应用
├── 知识库
├── 工具
├── 融资工作台  ◄── 本模块入口
└── 系统设置

融资工作台（左侧二级菜单）
├── 📊 工作台首页         /finance/overview
├── 📂 融资项目库         /finance/projects
├── 📦 材料整理           /finance/materials
├── 📝 流程文档           /finance/documents
├── 🔍 可行性初判         /finance/feasibility    [disabled · P2]
├── 📈 进度归集           /finance/progress       [disabled · P2]
├── 📡 实时资讯           /finance/intel          [disabled · P3]
├── 📄 模板管理           /finance/templates
└── 🛡️ 操作审计           /finance/audit
```

> 备注：disabled 菜单项保留入口但不可点击，hover 时显示"敬请期待 · 计划于 Phase 2/3 上线"。

### 3.2 页面布局规范

主操作页面统一采用 **三栏可塌缩布局**，与平台其他高密度业务页（如 `application` 工作流编辑器）一致：

| 区域 | 内容 | 默认状态 |
| --- | --- | --- |
| 左栏 | 项目侧边栏（项目列表 + 搜索 + 筛选） | 展开 280px |
| 中栏 | 主操作区（表单 / 列表 / 编辑器） | 自适应填充 |
| 右栏 | 详情抽屉（项目详情 / 历史版本 / 关联文档） | 默认折叠，按需展开 |

布局组件复用 `ui/src/components/layout-container/index.vue`；列表表格统一使用 Element Plus `el-table` + 平台已有 `pagination` 二次封装。

---

## 四、技术架构

### 4.1 后端 — apps/finance/ 结构

```
apps/finance/
├── __init__.py
├── apps.py                 # Django AppConfig
├── urls.py                 # 模块路由
├── models/
│   ├── __init__.py
│   ├── project.py          # FinanceProject
│   ├── materials_task.py   # MaterialsTask
│   ├── document_template.py# DocumentTemplate
│   ├── document_generation.py  # DocumentGeneration
│   └── audit_log.py        # FinanceAuditLog
├── views/                  # DRF ViewSet / APIView
├── serializers/            # DRF Serializer
├── service/
│   ├── materials_packager.py   # 材料整理业务编排
│   ├── document_generator.py   # 文档生成业务编排
│   └── sender.py               # 邮件/下载链接发送
├── tools/                  # 注册到 tools 框架的可调用工具
│   ├── docx_render.py      # docx 模板渲染
│   ├── zip_packager.py     # ZIP 打包
│   └── smtp_sender.py      # SMTP 发送
├── migrations/
└── tests/
```

设计要点：

- `service/` 是业务编排层，**调用 `tools/` 和 `apps/application/flow/` 工作流**，不直接写复杂逻辑
- `tools/` 同时注册到 `apps/tools` 的通用工具框架，使工作流节点也能调用
- `models/` 全部带 `workspace_id`、`create_time`、`update_time`、`is_deleted` 软删除字段

### 4.2 前端 — ui/src/views/finance/ 结构

```
ui/src/views/finance/
├── index.vue               # 模块根布局（左侧菜单容器）
├── overview/               # 工作台首页
│   └── index.vue
├── project/                # 融资项目库
│   ├── index.vue
│   ├── components/
│   │   ├── ProjectList.vue
│   │   ├── ProjectDetailDrawer.vue
│   │   └── ProjectFormDialog.vue
│   └── api.ts
├── materials/              # 材料整理
│   ├── index.vue
│   ├── components/
│   │   ├── TaskList.vue
│   │   ├── MaterialPreview.vue
│   │   ├── SensitivityBadge.vue
│   │   └── ReviewPanel.vue
│   └── api.ts
├── documents/              # 流程文档
│   ├── index.vue
│   ├── components/
│   │   ├── TemplatePicker.vue
│   │   ├── DocumentEditor.vue   # 基于 md-editor-v3 或 docx 预览
│   │   └── GenerationHistory.vue
│   └── api.ts
├── template/               # 模板管理
├── audit/                  # 操作审计日志
├── disabled/               # P2/P3 占位空页面（统一组件）
└── store/                  # Pinia store
    ├── project.ts
    ├── materials.ts
    └── documents.ts
```

### 4.3 与现有 MaxKB 模块的对接

| 现有模块 | 变更 | 说明 |
| --- | --- | --- |
| `apps/knowledge` | 新增 `Document.sensitivity_level` 字段；新增基于该字段的过滤逻辑 | 影响面：迁移脚本默认全部填 `internal`；list/detail API 透出新字段；前端文档详情页支持显示与编辑（仅有权限者） |
| `apps/application/flow` | 新增 2 个节点：`docx_render_node` / `zip_pack_node`；新增 2 个预置工作流 `__internal_materials_packager` / `__internal_document_generator` | 节点遵循 `i_step_node.INode` 契约；预置工作流不可被用户编辑，但可被克隆 |
| `apps/tools` | 新增 SMTP / ZIP / DOCX 三个自定义工具 | 同时供工作流节点和 `apps/finance/service/` 调用 |
| `apps/users` / `apps/system_manage` | 新增 5 个 `FINANCE:*` 权限码及默认角色绑定 | 详见第七章 |

---

## 五、数据模型

> 仅列字段清单，完整 DDL 在 Gate 2 数据底座阶段落地。

### 5.1 FinanceProject（融资项目）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| workspace_id | UUID | 多租户隔离 |
| name | varchar(200) | 项目名称 |
| code | varchar(64) | 内部编号，workspace 内唯一 |
| applicant | varchar(200) | 申请方（公司主体） |
| financing_type | varchar(32) | 申请类型（流贷/项目贷/债券/股权等） |
| counterparty | varchar(200) | 金融机构对手方 |
| amount | decimal(18,2) | 融资金额 |
| currency | varchar(8) | 币种，默认 CNY |
| stage | varchar(32) | 阶段枚举（intent/material/review/signed/closed） |
| status | varchar(16) | 状态（active/paused/canceled） |
| owner_user_id | UUID | 项目负责人 |
| risk_level | varchar(8) | 风险等级（low/mid/high） |
| description | text | 项目简介 |
| metadata | jsonb | 业务扩展字段 |
| create_time / update_time / is_deleted | — | 通用审计字段 |

### 5.2 MaterialsTask（材料整理任务）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| workspace_id | UUID | 多租户 |
| project_id | FK → FinanceProject | 关联项目 |
| applicant / financing_type / counterparty | varchar | 三因素冗余存储，便于查询 |
| status | varchar(16) | parsing/matching/selecting/reviewing/sending/done/failed |
| selected_document_ids | jsonb (array) | 选中的 knowledge.Document.id 列表 |
| workflow_run_id | UUID | 关联 `application/flow` 的运行实例 |
| zip_file_oss_key | varchar | 打包后 ZIP 在 OSS 的 key |
| reviewer_user_id | UUID nullable | 审核人 |
| review_comment | text | 审核备注 |
| sent_to | jsonb | 收件人列表（含邮箱、密送等） |
| sent_at | timestamp | 实际发送时间 |
| create_time / update_time / is_deleted | — | 通用字段 |

### 5.3 DocumentTemplate（公文模板）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| workspace_id | UUID | 多租户 |
| name | varchar(200) | 模板名（立项报告/可研/决议等） |
| category | varchar(32) | 分类 |
| docx_oss_key | varchar | 模板 docx 在 OSS 的 key |
| placeholders | jsonb | 占位符元信息（key、提示、是否 AI 填充） |
| version | int | 版本号，递增 |
| is_active | bool | 是否启用 |
| create_user_id | UUID | 创建人 |
| create_time / update_time / is_deleted | — | 通用字段 |

### 5.4 DocumentGeneration（文档生成任务）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| workspace_id | UUID | 多租户 |
| project_id | FK → FinanceProject | 关联项目 |
| template_id | FK → DocumentTemplate | 使用的模板 |
| template_version | int | 锁定的模板版本 |
| placeholder_values | jsonb | 用户输入的占位符值 |
| ai_generated_values | jsonb | AI 自动填充的占位符值 |
| workflow_run_id | UUID | 关联工作流运行 |
| output_oss_key | varchar | 生成后 docx 在 OSS 的 key |
| status | varchar(16) | generating/done/failed |
| create_user_id | UUID | 创建人 |
| create_time / update_time / is_deleted | — | 通用字段 |

### 5.5 FinanceAuditLog（操作审计日志）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| workspace_id | UUID | 多租户 |
| user_id | UUID | 操作人 |
| action | varchar(32) | 动作枚举（create/update/delete/review_pass/review_reject/send/download） |
| resource_type | varchar(32) | project/materials_task/document_generation/template |
| resource_id | UUID | 资源 id |
| ip | varchar(64) | 操作 IP |
| user_agent | varchar(256) | UA |
| diff | jsonb | 变更前后对比（敏感字段脱敏） |
| create_time | timestamp | 操作时间，不可更改 |

### 5.6 knowledge.Document.sensitivity_level（既有表 modification）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| sensitivity_level | varchar(16) | 取值 `public/internal/confidential/secret`，默认 `internal`；非空 |

迁移策略：

- 数据迁移：所有已有 Document 默认填 `internal`
- 索引：增加 `(workspace_id, sensitivity_level)` 复合索引
- 兼容：旧接口透出该字段但不强校验；finance 模块新接口强校验

---

## 六、API 设计

> 仅列端点与简要说明，完整请求/响应 schema 在 Gate 2/3/4 各自落地时补充。所有路径前缀为 `/api/finance/`。

### 6.1 融资项目

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/projects` | 列表，支持按 stage/applicant/financing_type 筛选 |
| POST | `/projects` | 创建项目 |
| GET | `/projects/{id}` | 详情 |
| PUT | `/projects/{id}` | 更新 |
| DELETE | `/projects/{id}` | 软删除 |
| POST | `/projects/{id}/transition` | 阶段流转（带前置校验） |

### 6.2 材料整理任务

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/materials` | 列表 |
| POST | `/materials` | 创建任务（三因素 + 项目） |
| GET | `/materials/{id}` | 详情 |
| POST | `/materials/{id}/parse` | 触发要素解析工作流 |
| POST | `/materials/{id}/match` | 触发知识库匹配 |
| PUT | `/materials/{id}/selection` | 更新候选文档选择 |
| POST | `/materials/{id}/submit-review` | 提交审核 |
| POST | `/materials/{id}/review` | 审核通过/驳回 |
| POST | `/materials/{id}/zip` | 触发打包 |
| POST | `/materials/{id}/send` | 发送（需二次确认 token） |

### 6.3 公文模板

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/templates` | 列表 |
| POST | `/templates` | 上传新模板（管理员） |
| GET | `/templates/{id}` | 详情 |
| POST | `/templates/{id}/new-version` | 上传新版本 |
| DELETE | `/templates/{id}` | 下架 |

### 6.4 文档生成

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/documents` | 生成历史列表 |
| POST | `/documents` | 创建生成任务（项目 + 模板 + 表单值） |
| GET | `/documents/{id}` | 详情 |
| POST | `/documents/{id}/regenerate` | 重新生成（保留占位符） |
| GET | `/documents/{id}/download` | 下载签名链接 |

### 6.5 审计日志

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/audit` | 日志列表（仅管理员），支持按 user/action/resource 过滤 |
| GET | `/audit/{id}` | 详情 |

---

## 七、权限设计

### 7.1 权限码定义

| 权限码 | 说明 |
| --- | --- |
| `FINANCE:VIEW` | 进入融资工作台、查看项目/材料/文档列表 |
| `FINANCE:EDIT` | 创建/修改项目、发起材料任务、生成文档 |
| `FINANCE:REVIEW` | 审核材料包、审核文档发布 |
| `FINANCE:SEND` | 执行对外发送动作（邮件/下载链接） |
| `FINANCE:ADMIN` | 模板管理、审计日志查看、敏感字段编辑 |

### 7.2 默认角色绑定矩阵

| 权限码 \ 角色 | ADMIN | WORKSPACE_MANAGE | USER（业务员） |
| --- | :---: | :---: | :---: |
| FINANCE:VIEW | ✓ | ✓ | ✓ |
| FINANCE:EDIT | ✓ | ✓ | ✓ |
| FINANCE:REVIEW | ✓ | ✓ | — |
| FINANCE:SEND | ✓ | ✓ | — |
| FINANCE:ADMIN | ✓ | — | — |

> 注：业务员可发起任务，但审核与发送必须由 `WORKSPACE_MANAGE` 及以上完成，构成天然分权。

---

## 八、安全策略

### 8.1 敏感等级硬约束（白名单制）

- 所有 `knowledge.Document` 默认 `sensitivity_level = internal`
- 材料打包前：后端依据当前操作人的角色对候选文档做密级过滤
  - 无 `FINANCE:ADMIN` 权限的用户：可见 `public / internal`，不可见 `confidential / secret`
  - `FINANCE:ADMIN`：可见全部，但下载/打包 `secret` 文档仍需二次身份认证（OTP/动态码）
- 发送前：再次执行密级校验，任何包含 `secret` 的材料包默认禁止外发，须管理员显式审批

### 8.2 发送二次确认 + 强制审计

- 所有对外发送动作必须先获取 `confirm_token`（前端弹窗 + 输入"我已确认"），有效期 5 分钟
- 发送动作写入 `FinanceAuditLog`，且日志不允许通过 API 删除或更新（DB 层加触发器保护）

### 8.3 模板上传管理员权限

- 仅 `FINANCE:ADMIN` 可上传/更新公文模板
- 上传时后端解析 docx，**拒绝包含宏（VBA）、嵌入对象（OLE）或外部链接**的文件
- 模板版本不可销毁，下架仅置 `is_active = false`

### 8.4 SMTP 凭证 workspace 级加密存储

- 每个 workspace 维护独立 SMTP 配置
- 凭证字段（password / app_password）在 DB 层使用 Fernet 对称加密（密钥来自环境变量 `MAXKB_SECRET_KEY`）
- API 列表/详情接口不回显密文，仅返回掩码

### 8.5 跨 workspace 越权防护

- 所有 ViewSet 强制注入 `workspace_id` 过滤；任何 `get_queryset` 不加 workspace 过滤的 PR 在 CI 阶段被 lint 规则拦截（自定义 ruff 规则 + code review checklist）
- 外键引用跨 workspace 的资源（如 `knowledge.Document`）在写入时校验同 workspace

---

## 九、实施路线 — 6 个 Gate

> 每个 Gate 都是一个独立可演示的里程碑，验收不通过不能进入下一 Gate。预估按 1 人全职估算，可并行压缩。

### Gate 0 — 启动准备

**目标**：完成立项、达成设计共识、备齐先决条件。

关键任务：
1. 输出本设计文档 v0.1（即本文）
2. 邀请业务方确认 5 项功能优先级
3. 收集首批 3-5 份公文模板（立项报告 / 董事会决议 / 可研框架）
4. 收集示例融资场景三因素清单（≥5 个）
5. 数据库迁移影响评估（`knowledge.Document` schema 改动）
6. 创建 feature flag `FINANCE_MODULE_ENABLED`（默认关闭）

验收标准：
1. 设计文档评审通过
2. 模板与场景素材已归档至共享目录
3. feature flag 接入 `apps/maxkb/conf.py`
4. 立项 issue 创建完毕（每个 Gate 一个 epic）
5. 项目排期对齐

演示场景：评审会过稿即视为完成。

**预估工时：—**（计划阶段，已并入 Gate 1）

---

### Gate 1 — 骨架 & 菜单

**目标**：搭建 `apps/finance` Django 应用骨架 + 前端菜单/路由骨架，全链路打通空页面。

关键任务：
1. 新建 `apps/finance/` 应用、`apps.py`、`urls.py`、空 `views.py`、`models.py`
2. 在 `apps/maxkb/urls/web.py` 挂载 `/api/finance/`
3. 前端新建 `ui/src/views/finance/index.vue` 及 9 个子菜单空页面
4. 接入左侧菜单，P2/P3 项置灰
5. 接入 i18n（zh-cn / en / zh-hant）
6. 接入 feature flag：菜单显隐由 `FINANCE_MODULE_ENABLED` 控制
7. 添加 `FINANCE:VIEW` 权限码（仅一个），ADMIN 角色默认拥有
8. 单元测试覆盖路由 200/403 场景

验收标准：
1. 开启 flag 后菜单出现，关闭后消失
2. 9 个菜单项均可点击进入空页面（P2/P3 显示占位文案）
3. 无 `FINANCE:VIEW` 的用户访问任何子页返回 403
4. ruff / vue-tsc 通过
5. Django `python apps/manage.py test finance` 通过
6. 文档章节"三、四"的目录结构与实际代码一致

演示场景：登录平台 → 左侧菜单看到"融资工作台" → 进入 9 个子页 → 三个 P2/P3 项灰显。

**预估工时：≈ 5 人日**

---

### Gate 2 — 融资项目库 & 数据底座

**目标**：完整 CRUD 融资项目，同时落地 `knowledge.Document.sensitivity_level` 字段。

关键任务：
1. 落地 `FinanceProject` 模型与迁移
2. 落地 `FinanceAuditLog` 模型与触发器
3. 落地 `knowledge.Document.sensitivity_level` 字段及迁移脚本
4. 实现项目库列表 / 详情 / 表单 / 阶段流转 API
5. 前端项目库三栏页面、项目表单、阶段流转交互
6. 接入审计日志（所有写动作落审计表）
7. 接入 `FINANCE:EDIT` 权限码与默认角色

验收标准：
1. 项目可创建/编辑/软删除/阶段流转
2. 列表支持按 stage、applicant、financing_type 筛选
3. 所有写动作生成审计日志，且日志不可被 API 删除
4. `knowledge.Document` 详情页可见且 ADMIN 可编辑 `sensitivity_level`
5. 数据库迁移在已有数据上零报错
6. 跨 workspace 访问返回 404（不泄露存在性）
7. 单元测试覆盖率 ≥ 70%

演示场景：创建一个虚拟项目"XX 园区开发流贷-2026Q2" → 流转至 material 阶段 → 在审计日志查到三条记录。

**预估工时：≈ 5 人日**

---

### Gate 3 — 流程文档 MVP（先做这个）

**目标**：跑通"选模板 → 填占位符 → AI 部分自动填充 → 生成 docx → 下载"全链路。先于材料整理落地，因模板上传更可控、风险面更小。

关键任务：
1. 落地 `DocumentTemplate` / `DocumentGeneration` 模型
2. 实现模板上传 API（含恶意 docx 校验）
3. 实现 `tools/docx_render.py`（docxtpl 封装）
4. 在 `application/flow/step_node/` 新增 `docx_render_node`
5. 注册预置工作流 `__internal_document_generator`，包含：占位符校验 → AI 填充节点 → docx_render
6. 前端：模板管理页（上传/版本）+ 文档生成页（选模板 → 表单 → 预览/下载）
7. 前端 docx 预览组件（用 mammoth.js 或后端预览图）
8. AI 占位符标识规范：模板中 `{{ai:章节名}}` 形式

验收标准：
1. 管理员可上传 docx 模板，非管理员不可
2. 含 VBA/OLE 的 docx 被拒绝
3. 模板版本可累加，旧版本可被生成任务锁定引用
4. 生成任务成功率 ≥ 95%（基于内置 3 份业务模板）
5. AI 占位符填充内容来源可追溯（写入 `ai_generated_values`）
6. 生成的 docx 在 MS Word / WPS 中样式无错位
7. 单元测试覆盖核心路径 ≥ 70%
8. 审计日志记录生成与下载

演示场景：选择"董事会决议"模板 → 项目下拉自动带出公司主体 → AI 自动生成"决议内容"章节 → 下载 docx 在 WPS 中打开格式正确。

**预估工时：≈ 10 人日**

---

### Gate 4 — 材料整理 MVP

**目标**：跑通"输入三因素 → 知识库匹配 → 人工选择 → 打包 → 待审"链路（不含发送）。

关键任务：
1. 落地 `MaterialsTask` 模型
2. 实现要素解析工作流节点（NLP 抽取三因素结构化）
3. 实现知识库匹配工作流（结合密级过滤）
4. 实现 `tools/zip_packager.py` 与 `zip_pack_node`
5. 注册预置工作流 `__internal_materials_packager`
6. 前端：材料整理列表 + 任务向导页面（步骤条：解析 → 匹配 → 选择 → 打包）
7. 候选文档列表附带密级徽标（`SensitivityBadge.vue`）
8. 任务状态机：parsing/matching/selecting/reviewing
9. 接入 `FINANCE:REVIEW` 权限码（本 Gate 仅做"submit-review"动作，审核流程在 Gate 5）

验收标准：
1. 三因素正确解析，覆盖至少 5 个业务场景
2. 候选文档默认按密级排序，secret 文档对非 ADMIN 不可见
3. 用户可勾选/反选并保存中间状态
4. 打包后 ZIP 在 OSS 可下载
5. 任务可"提交审核"切换到 reviewing 状态
6. 工作流运行失败时任务状态置 failed 并保留错误信息
7. 单元测试 + 集成测试覆盖核心路径

演示场景：输入"XX 公司 / 流动资金贷款 / 工商银行" → 系统自动找出 12 份候选材料（5 份机密对当前用户隐藏） → 用户勾选 8 份 → 打包成 ZIP → 提交审核。

**预估工时：≈ 8 人日**

---

### Gate 5 — 审核 & 发送闭环

**目标**：完成材料/文档的审核与对外发送，形成端到端闭环。

关键任务：
1. 实现审核 API（review_pass / review_reject）
2. 前端审核面板（含密级核查清单、审核意见、签字时间戳）
3. 实现 `tools/smtp_sender.py` 与发送 API（带 `confirm_token` 机制）
4. workspace 级 SMTP 配置页（凭证加密存储）
5. 发送动作的二次确认 UI
6. 接入 `FINANCE:SEND` 权限
7. 审计日志增强：发送动作记录收件人、附件 hash、密级摘要
8. 邮件失败重试机制（指数退避，最多 3 次）

验收标准：
1. 无 `FINANCE:REVIEW` 的用户看不到审核按钮
2. 审核驳回会回退任务到 selecting 状态并保留意见
3. 发送动作无 `confirm_token` 必然失败
4. SMTP 凭证 API 不回显明文
5. 一次完整发送在审计日志中可还原全部细节
6. 发送失败有用户可见的错误提示
7. 端到端集成测试通过（项目 → 材料 → 审核 → 发送 → 审计可查）

演示场景：管理员审核 Gate 4 提交的材料包 → 通过 → 录入收件人 → 二次确认 → 发送 → 收件邮箱收到 ZIP → 审计日志可追溯。

**预估工时：≈ 7 人日**

---

### Gate 6 — 打磨 & 上线

**目标**：性能优化、UI 打磨、文档齐备、灰度发布。

关键任务：
1. 性能压测（材料匹配 ≤ 3s、文档生成 ≤ 10s）
2. 大材料包打包流式处理（避免 OOM）
3. 工作台首页（数据看板：在途项目数、待审数、近期发送趋势）
4. 操作审计页（含导出 CSV）
5. 用户手册 & 视频演示
6. i18n 完整覆盖（zh-cn / en / zh-hant）
7. 灰度发布开关（按 workspace 名单启用）
8. 安全自查清单逐项过一遍（见第十二章）

验收标准：
1. 关键接口 P95 延迟达标
2. 灰度 workspace 试用 ≥ 3 天无 P0 缺陷
3. 用户手册 review 通过
4. 安全自查清单全 ✓
5. 所有 disabled 菜单项保留占位
6. 总体测试覆盖率 ≥ 70%
7. 上线 runbook + 回滚方案归档

演示场景：试点 workspace 完整跑一个真实融资项目从立项到发送，过程在工作台首页可视化追踪。

**预估工时：≈ 7 人日**

---

> 6 个 Gate 合计 **≈ 47 人日**（约 9-10 周单人节奏；如双人并行可压缩至 5-6 周）。

---

## 十、风险登记与回滚

### 10.1 风险登记

| 风险 | 概率 | 影响 | 应对 |
| --- | --- | --- | --- |
| `docxtpl` 渲染异常（复杂表格/合并单元格丢失） | 中 | 高 | Gate 0 用真实模板做 POC；建立"已验证模板清单"；提供模板调试工具 |
| 敏感等级误标（公开材料被标 secret 或反之） | 中 | 高 | 提供批量重标 UI；首次启用强制 ADMIN 复核全部 Document；增加密级变更审计 |
| SMTP 滥用 / 垃圾邮件 | 低 | 高 | workspace 级速率限制（每小时 ≤ 50 封）；收件域名白/黑名单；管理员熔断开关 |
| AI 占位符填充质量不稳定 | 高 | 中 | 占位符必须可被人工编辑；生成历史保留 AI 原始输出；引入"人审必经"开关 |
| 模板版本漂移（生成文档引用了已下架模板） | 低 | 中 | `DocumentGeneration` 锁定 `template_version`；下架仅置 inactive 不删除 |
| 工作流并发瓶颈（材料匹配排队） | 中 | 中 | Celery 队列分级（finance.matching 独立队列）；超时降级为同步小批匹配 |
| `knowledge.Document` schema 改动影响存量 | 中 | 高 | 迁移脚本带回滚；预生产环境演练；feature flag 控制新字段强校验 |

### 10.2 回滚预案

- **Gate 级独立回滚**：每个 Gate 在合并前都打 tag，可单独回滚到上一 Gate 的状态
- **feature flag**：`FINANCE_MODULE_ENABLED` 控制模块整体开关，紧急情况关闭即可让模块完全隐藏（不影响其他模块）
- **数据库回滚**：所有迁移成对出现（forward + backward），`knowledge.Document.sensitivity_level` 字段保留可空兼容期一个版本
- **紧急隐藏开关**：左侧菜单项受 flag 控制；前端构建产物保留但不渲染入口
- **数据保留**：即便模块下线，已生成的 docx / ZIP 文件在 OSS 至少保留 90 天

---

## 十一、Definition of Done

每个 Gate 合并到 v2 主干前必须满足：

1. **代码质量**：`uv run ruff check .` 与 `uv run ruff format --check .` 通过
2. **类型检查**：前端 `npm run type-check` 通过；Python 关键模块加 type hint
3. **测试**：`python apps/manage.py test finance` 通过；新增逻辑覆盖率 ≥ 70%
4. **文档**：本设计文档对应章节同步更新版本号；API 接口在 OpenAPI/DRF schema 中可见
5. **代码审查**：至少 1 人 review 通过；涉及安全/权限的 PR 需 2 人 review
6. **手动验证**：核对 Gate 验收标准全部 ✓；操作 demo 录屏归档
7. **审计**：本 Gate 引入的所有写接口确认在 `FinanceAuditLog` 留痕
8. **回滚演练**：至少在 dev 环境演练一次回滚脚本
9. **i18n**：所有用户可见文案至少有 zh-cn 与 en 两版

---

## 十二、安全自查清单（上线前）

在 Gate 6 上线前由独立审计角色逐项核对：

1. **跨 workspace 越权**：随机抽取 5 个 API，伪造 workspace_id 必须返回 404
2. **文件直链签名**：OSS 文件链接带签名且有效期 ≤ 15 分钟；过期链接拒绝访问
3. **越权审核/发送**：无 `FINANCE:REVIEW` / `FINANCE:SEND` 权限的用户调用对应 API 必须返回 403
4. **敏感等级绕过**：绕过前端在后端直接传 `secret` 文档 id 必须被拒
5. **SMTP 凭证泄漏**：列表/详情接口、日志、报错堆栈均不出现明文密码
6. **恶意 docx**：上传含 VBA / OLE / 外部链接的 docx 必须被拒
7. **占位符注入**：占位符值中包含 docx 模板语法应被转义，不可触发模板逻辑
8. **审计日志篡改**：尝试通过 API/SQL 删除或修改 `FinanceAuditLog` 必须失败
9. **二次确认绕过**：发送 API 不带 `confirm_token` 或 token 过期必须返回 400

任一项不通过即阻断上线。

---

## 十三、版本记录

| 版本 | 日期 | 变更 | 作者 |
| --- | --- | --- | --- |
| v0.1 | 2026-05-13 | 初版，Gate 1 启动同步落地：架构 / 数据模型 / API / 权限 / 6-Gate 路线图 / 风险 / 安全清单 | Finance Workspace 小组 |


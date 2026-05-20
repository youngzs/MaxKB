/**
 * Finance workspace — TypeScript types (Gate 2/3 Track B/C).
 * Mirrors the backend API contract.
 */

export type ProjectType = 'bank_loan' | 'bond' | 'trust' | 'abs' | 'other'

export type ProjectStatus = 'preparing' | 'materials' | 'engaging' | 'landed' | 'terminated'

export interface Project {
  id: string
  workspace_id: string
  name: string
  code: string
  project_type: ProjectType
  /** Decimal serialized as a string by DRF; may be null when not set. */
  target_amount: string | null
  currency: string
  status: ProjectStatus
  region: string
  industry_code: string
  knowledge_base_ids: string[]
  description: string
  /** P2 进度归集：项目负责人 / 主要对手方 / 当前子阶段 key。 */
  owner_id: string | null
  counterparty: string
  current_stage_key: string
  created_by: string
  created_at: string
  updated_at: string
}

/** 创建项目时单个子阶段的计划完成时间（DR-P2-04，仅创建生效）。 */
export interface StagePlanInput {
  stage_key: string
  planned_at: string | null
}

export interface ProjectInput {
  name: string
  project_type: ProjectType
  code?: string
  target_amount?: string | null
  currency?: string
  status?: ProjectStatus
  region?: string
  industry_code?: string
  knowledge_base_ids?: string[]
  description?: string
  owner_id?: string | null
  counterparty?: string
  /** 仅创建项目时携带 —— 一组按类型模板列出的阶段计划完成时间。 */
  stage_plans?: StagePlanInput[]
}

/** 单个子阶段模板项（GET stage-templates 返回）。 */
export interface StageTemplateItem {
  stage_key: string
  label: string
  maps_to_status: ProjectStatus
  order: number
}

/** project_type -> 有序子阶段模板。 */
export type StageTemplatesMap = Record<ProjectType, StageTemplateItem[]>

/* ──────────────────────────────────────────────────────────────────────────
 *  Progress / Stage records (P2 Gate 2/3)
 * ─────────────────────────────────────────────────────────────────────── */

export type StageStatus = 'pending' | 'active' | 'done' | 'skipped'

/** 单条阶段记录（GET project/<pk>/stages 与 progress/gantt 返回）。 */
export interface StageRecord {
  id: string
  workspace_id: string
  project_id: string
  stage_key: string
  stage_order: number
  planned_at: string | null
  actual_at: string | null
  owner_id: string | null
  entered_at: string | null
  status: StageStatus
  note: string
  created_at: string
  updated_at: string
  /** 模板派生的阶段中文名 —— gantt / stages 端点附带。 */
  stage_label?: string
}

/** 运行时风险等级（progress/gantt 实时计算，不落库）。 */
export type RiskLevel = 'none' | 'yellow' | 'red'

/** progress/gantt 里的单个项目：项目字段 + 阶段记录 + 风险。 */
export interface GanttProject extends Project {
  stages: StageRecord[]
  risk: RiskLevel
  /** 风险原因代码（dwell_red / deadline_yellow / materials_failed …），前端 i18n 成文案。 */
  risk_reasons: string[]
}

export interface GanttResponse {
  projects: GanttProject[]
}

export interface CounterpartyShare {
  counterparty: string
  count: number
}

/** progress/dashboard 驾驶舱聚合 KPI。 */
export interface DashboardData {
  total_count: number
  in_flight_count: number
  /** Decimal 序列化为字符串。 */
  in_flight_amount: string
  landed_count: number
  terminated_count: number
  /** 通过率百分比；无已决项目时为 null。 */
  pass_rate: number | null
  /** 平均周期（天）；无落地项目时为 null。 */
  avg_cycle_days: number | null
  counterparty_share: CounterpartyShare[]
  risk: { yellow: number; red: number }
}

export interface GanttParams {
  project_type?: ProjectType | ''
  status?: ProjectStatus | ''
  owner_id?: string
}

/** PUT project/<pk>/stages/<stage_key> 请求体（partial）。 */
export interface StageUpdateInput {
  planned_at?: string | null
  owner_id?: string | null
  note?: string
}

export interface ListParams {
  keyword?: string
  status?: ProjectStatus | ''
  page?: number
  size?: number
}

export interface PageResult<T> {
  records: T[]
  total: number
  current: number
  size: number
}

/* ──────────────────────────────────────────────────────────────────────────
 *  Template (Gate 3 Track C)
 *  Mount: /admin/api/finance/workspace/<workspace_id>/template
 * ─────────────────────────────────────────────────────────────────────── */

export type TemplateScenario =
  | 'internal_report'
  | 'meeting'
  | 'system_process'
  | 'other'

export type PlaceholderType = 'text' | 'long_text' | 'number' | 'date' | 'enum'

export interface Placeholder {
  /** Immutable, taken from `{{key}}` in the source docx. */
  key: string
  /** Display label, editable. */
  label: string
  type: PlaceholderType
  required: boolean
  /** Single-sentence hint for the AI fill action. */
  ai_hint: string
  /** Options shown when `type === 'enum'`. */
  enum_options: string[]
}

export interface Template {
  id: string
  workspace_id: string
  name: string
  scenario: TemplateScenario
  docx_oss_key: string
  placeholders: Placeholder[]
  version: number
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface TemplateUpdate {
  name?: string
  scenario?: TemplateScenario
  is_active?: boolean
  placeholders?: Placeholder[]
}

export interface TemplatePlaceholderSuggestResult {
  placeholders: Placeholder[]
}

export interface TemplateListParams {
  scenario?: TemplateScenario | ''
  page?: number
  size?: number
}

/* ──────────────────────────────────────────────────────────────────────────
 *  Generation (Gate 3 Track C)
 *  Mount: /admin/api/finance/workspace/<workspace_id>/generation
 * ─────────────────────────────────────────────────────────────────────── */

export type GenerationStatus =
  | 'generating'
  | 'pending_review'
  | 'confirmed'
  | 'revoked'
  | 'failed'

export interface Generation {
  id: string
  workspace_id: string
  project_id: string
  template_id: string
  template_version_snapshot: number
  placeholder_values: Record<string, string | number>
  workflow_run_id: string | null
  output_oss_key: string
  status: GenerationStatus
  error_message: string
  reviewer_id: string | null
  reviewed_at: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface GenerationCreate {
  project_id: string
  template_id: string
  placeholder_values: Record<string, string | number>
}

export interface GenerationListParams {
  project_id?: string
  status?: GenerationStatus | ''
  page?: number
  size?: number
}

export interface AIFillRequest {
  template_id: string
  project_id: string
  placeholder_keys: string[]
}

export type AIFillResponse = Record<string, string>

export interface GenerationPreview {
  html: string
}

/* ──────────────────────────────────────────────────────────────────────────
 *  Materials Task (Gate 4 Track C)
 *  Mount: /admin/api/finance/workspace/<workspace_id>/materials-task
 * ─────────────────────────────────────────────────────────────────────── */

export type MaterialsTaskStatus =
  | 'draft'
  | 'parsing'
  | 'matching'
  | 'pending_review'
  | 'approved'
  | 'sent'
  | 'rejected'
  | 'failed'

export type SensitivityLevel =
  | 'public'
  | 'internal'
  | 'confidential'
  | 'secret'

export interface ParsedItem {
  /** Stable identifier — links from MatchedDocument.item_key. */
  key: string
  label: string
  description: string
  required: boolean
}

export interface MatchedDocument {
  /** Refers to ParsedItem.key. */
  item_key: string
  document_id: string
  document_name: string
  sensitivity_level: SensitivityLevel
  /** 0..1 similarity score. */
  score: number
  /** Highlight snippet from the matching paragraph. */
  snippet: string
  /** AI-generated short summary for this document in this task context. */
  ai_summary: string
  /** Client-inferred (not server-returned): true when over current user clearance. */
  is_locked?: boolean
}

export interface MaterialsTask {
  id: string
  workspace_id: string
  project_id: string
  title: string
  requirement_text: string
  requirement_file_oss_key: string
  parsed_items: ParsedItem[]
  matched_documents: MatchedDocument[]
  /** document_ids that the user has marked as selected for the package. */
  selected_documents: string[]
  zip_oss_key: string
  status: MaterialsTaskStatus
  reviewer_id: string | null
  reviewed_at: string | null
  review_comment: string
  error_message: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface MaterialsTaskListParams {
  project_id?: string
  status?: MaterialsTaskStatus | ''
  page?: number
  size?: number
}

export interface MaterialsTaskSelectionUpdate {
  selected_documents: string[]
  /** Optional override of the matched_documents snapshot (e.g. when manually adding docs). */
  matched_documents?: MatchedDocument[]
}

export interface MaterialsTaskReviewBody {
  action: 'pass' | 'reject'
  comment?: string
}

/* ──────────────────────────────────────────────────────────────────────────
 *  Audit Log (Gate 5 Track C)
 *  Mount: /admin/api/finance/workspace/<workspace_id>/audit-log
 * ─────────────────────────────────────────────────────────────────────── */

export type AuditTargetType =
  | 'PROJECT'
  | 'MATERIALS_TASK'
  | 'DOC_TEMPLATE'
  | 'DOC_GENERATION'
  | 'SMTP_CONFIG'
  | 'OTHER'

export type AuditAction =
  | 'CREATE'
  | 'UPDATE'
  | 'DELETE'
  | 'READ'
  | 'REVIEW_PASS'
  | 'REVIEW_REJECT'
  | 'SEND'
  | 'DOWNLOAD'

export interface AuditLogEntry {
  id: string
  workspace_id: string
  actor_id: string
  target_type: AuditTargetType
  target_id: string | null
  action: AuditAction
  /** Redacted JSON snapshot of the inbound request (path, method, body, query). */
  payload: Record<string, unknown>
  ip: string | null
  user_agent: string
  created_at: string
}

export interface AuditLogListParams {
  target_type?: AuditTargetType | ''
  action?: AuditAction | ''
  actor_id?: string
  target_id?: string
  date_from?: string
  date_to?: string
  keyword?: string
  page?: number
  size?: number
}

/* ──────────────────────────────────────────────────────────────────────────
 *  SMTP / Email / Send (Gate 5 Track B)
 *  Mounts under /admin/api/finance/workspace/<workspace_id>
 * ─────────────────────────────────────────────────────────────────────── */

export interface SmtpConfig {
  id: string
  workspace_id: string
  name: string
  host: string
  port: number
  username: string
  from_email: string
  from_name: string
  use_tls: boolean
  use_ssl: boolean
  is_default: boolean
  /** True iff a password is currently stored. Plaintext NEVER returned. */
  has_password: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface SmtpConfigCreate {
  name: string
  host: string
  port: number
  username: string
  password: string
  from_email: string
  from_name?: string
  use_tls?: boolean
  use_ssl?: boolean
  is_default?: boolean
}

export interface SmtpConfigUpdate {
  name?: string
  host?: string
  port?: number
  username?: string
  /** Blank/omitted → keep existing password. */
  password?: string
  from_email?: string
  from_name?: string
  use_tls?: boolean
  use_ssl?: boolean
  is_default?: boolean
}

export interface SmtpTestRequest {
  to_address: string
}

export interface SmtpTestResponse {
  success: boolean
  error: string | null
}

export type EmailTemplateScenario =
  | 'materials'
  | 'progress_report'
  | 'general'
  | 'other'

export interface EmailTemplate {
  id: string
  workspace_id: string
  name: string
  subject: string
  body_text: string
  body_html: string
  scenario: EmailTemplateScenario
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface EmailTemplateCreate {
  name: string
  subject: string
  body_text: string
  body_html?: string
  scenario?: EmailTemplateScenario
  is_active?: boolean
}

export type EmailTemplateUpdate = Partial<EmailTemplateCreate>

export type EmailSendStatus =
  | 'queued'
  | 'sending'
  | 'sent'
  | 'failed'
  | 'retried'

export interface EmailSendLog {
  id: string
  workspace_id: string
  target_type: string
  target_id: string | null
  smtp_config_id: string | null
  email_template_id: string | null
  to_addresses: string[]
  cc_addresses: string[]
  subject: string
  body_preview: string
  attachment_keys: string[]
  status: EmailSendStatus
  error_message: string
  retry_count: number
  sent_by: string
  sent_at: string | null
  created_at: string
}

export interface MaterialsTaskSendBody {
  smtp_config_id: string
  email_template_id: string
  to_addresses: string[]
  cc_addresses?: string[]
  extra_context?: Record<string, string>
  attach_zip?: boolean
}

export interface EmailSendLogListParams {
  target_type?: string
  target_id?: string
  status?: EmailSendStatus | ''
  page?: number
  size?: number
}

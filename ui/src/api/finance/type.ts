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
  created_by: string
  created_at: string
  updated_at: string
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

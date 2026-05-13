/**
 * Finance workspace — TypeScript types (Gate 2 Track B).
 * Mirrors the backend Project API contract.
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

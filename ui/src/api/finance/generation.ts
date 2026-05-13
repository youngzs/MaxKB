import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get, post, exportFile } from '@/request/index'
import type {
  AIFillRequest,
  AIFillResponse,
  Generation,
  GenerationCreate,
  GenerationListParams,
  GenerationPreview,
  PageResult,
} from './type'

/**
 * Finance generation API client (Gate 3 Track C).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/generation`
 */

const buildPrefix = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/generation`

/**
 * GET /finance/workspace/<wid>/generation?project_id=&status=&page=&size=
 */
export const listGenerations: (
  workspaceId: string,
  params?: GenerationListParams,
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<Generation>>> = (workspaceId, params, loading) => {
  return get(`${buildPrefix(workspaceId)}/`, params, loading)
}

/**
 * GET /finance/workspace/<wid>/generation/<pk>
 */
export const getGeneration: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<Generation>> = (workspaceId, id, loading) => {
  return get(`${buildPrefix(workspaceId)}/${id}`, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/generation
 */
export const createGeneration: (
  workspaceId: string,
  body: GenerationCreate,
  loading?: Ref<boolean>,
) => Promise<Result<Generation>> = (workspaceId, body, loading) => {
  return post(`${buildPrefix(workspaceId)}/`, body, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/generation/<pk>/confirm
 */
export const confirmGeneration: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<Generation>> = (workspaceId, id, loading) => {
  return post(`${buildPrefix(workspaceId)}/${id}/confirm`, undefined, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/generation/<pk>/revoke
 */
export const revokeGeneration: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<Generation>> = (workspaceId, id, loading) => {
  return post(`${buildPrefix(workspaceId)}/${id}/revoke`, undefined, undefined, loading)
}

/**
 * GET /finance/workspace/<wid>/generation/<pk>/preview
 * Returns sanitized HTML from server-side mammoth rendering.
 */
export const fetchPreview: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<GenerationPreview>> = (workspaceId, id, loading) => {
  return get(`${buildPrefix(workspaceId)}/${id}/preview`, undefined, loading)
}

/**
 * GET /finance/workspace/<wid>/generation/<pk>/download
 * Triggers a browser save dialog using the shared file-export helper which
 * extracts the filename from the `Content-Disposition` header.
 */
export const downloadGeneration: (
  workspaceId: string,
  id: string,
  fallbackName: string,
  loading?: Ref<boolean>,
) => Promise<unknown> = (workspaceId, id, fallbackName, loading) => {
  return exportFile(
    fallbackName,
    `${buildPrefix(workspaceId)}/${id}/download`,
    undefined,
    loading,
  )
}

/**
 * POST /finance/workspace/<wid>/generation/ai-fill
 * Returns a map of `{<placeholder_key>: <generated_text>}`.
 */
export const aiFillPlaceholders: (
  workspaceId: string,
  body: AIFillRequest,
  loading?: Ref<boolean>,
) => Promise<Result<AIFillResponse>> = (workspaceId, body, loading) => {
  return post(`${buildPrefix(workspaceId)}/ai-fill`, body, undefined, loading)
}

export default {
  listGenerations,
  getGeneration,
  createGeneration,
  confirmGeneration,
  revokeGeneration,
  fetchPreview,
  downloadGeneration,
  aiFillPlaceholders,
}

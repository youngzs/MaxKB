import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get, post, put, del, exportFile } from '@/request/index'
import type {
  MaterialsTask,
  MaterialsTaskListParams,
  MaterialsTaskReviewBody,
  MaterialsTaskSelectionUpdate,
  PageResult,
} from './type'

/**
 * Finance materials-task API client (Gate 4 Track C).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/materials-task`
 * The axios instance prefixes `/admin/api`, so paths here start with `/finance/...`.
 */

const buildPrefix = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/materials-task`

/**
 * GET /finance/workspace/<wid>/materials-task/?project_id=&status=&page=&size=
 */
export const listTasks: (
  workspaceId: string,
  params?: MaterialsTaskListParams,
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<MaterialsTask>>> = (
  workspaceId,
  params,
  loading,
) => {
  return get(`${buildPrefix(workspaceId)}`, params, loading)
}

/**
 * GET /finance/workspace/<wid>/materials-task/<pk>
 */
export const getTask: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, loading) => {
  return get(`${buildPrefix(workspaceId)}/${id}`, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/materials-task/ (multipart/form-data)
 * Body: project_id + title + (requirement_text OR file).
 * The shared `post()` helper hands `FormData` straight to axios which sets
 * the `Content-Type` header (with boundary) automatically.
 */
export const createTask: (
  workspaceId: string,
  body: {
    project_id: string
    title: string
    requirement_text?: string
    file?: File
  },
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, body, loading) => {
  const fd = new FormData()
  fd.append('project_id', body.project_id)
  fd.append('title', body.title)
  if (body.requirement_text) {
    fd.append('requirement_text', body.requirement_text)
  }
  if (body.file) {
    fd.append('file', body.file)
  }
  return post(`${buildPrefix(workspaceId)}`, fd, undefined, loading)
}

/**
 * PUT /finance/workspace/<wid>/materials-task/<pk>
 * Partial update of editable fields (DRAFT / FAILED / PARSING / MATCHING).
 * Body shape:
 *   { title?, requirement_text?, parsed_items?: [{key,label,description?,required?}] }
 */
export const updateTask: (
  workspaceId: string,
  id: string,
  body: {
    title?: string
    requirement_text?: string
    parsed_items?: Array<{
      key: string
      label: string
      description?: string
      required?: boolean
    }>
  },
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, body, loading) => {
  return put(`${buildPrefix(workspaceId)}/${id}`, body, undefined, loading)
}

/**
 * DELETE /finance/workspace/<wid>/materials-task/<pk>
 */
export const deleteTask: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<null>> = (workspaceId, id, loading) => {
  return del(`${buildPrefix(workspaceId)}/${id}`, undefined, {}, loading)
}

/**
 * POST /finance/workspace/<wid>/materials-task/<pk>/parse
 * Server triggers requirement parsing; transitions task -> `parsing` then back to `draft`.
 */
export const parseRequirements: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, loading) => {
  return post(
    `${buildPrefix(workspaceId)}/${id}/parse`,
    undefined,
    undefined,
    loading,
  )
}

/**
 * POST /finance/workspace/<wid>/materials-task/<pk>/match
 * Server runs vector search for each parsed item; transitions through `matching`.
 */
export const matchDocuments: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, loading) => {
  return post(
    `${buildPrefix(workspaceId)}/${id}/match`,
    undefined,
    undefined,
    loading,
  )
}

/**
 * PUT /finance/workspace/<wid>/materials-task/<pk>/selection
 */
export const updateSelection: (
  workspaceId: string,
  id: string,
  body: MaterialsTaskSelectionUpdate,
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, body, loading) => {
  return put(`${buildPrefix(workspaceId)}/${id}/selection`, body, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/materials-task/<pk>/summarize
 * Regenerates ai_summary for selected docs.
 */
export const summarize: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, loading) => {
  return post(
    `${buildPrefix(workspaceId)}/${id}/summarize`,
    undefined,
    undefined,
    loading,
  )
}

/**
 * POST /finance/workspace/<wid>/materials-task/<pk>/pack
 * Packs selected docs (plus the AI summary index) into a zip; populates `zip_oss_key`.
 */
export const packZip: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, loading) => {
  return post(
    `${buildPrefix(workspaceId)}/${id}/pack`,
    undefined,
    undefined,
    loading,
  )
}

/**
 * POST /finance/workspace/<wid>/materials-task/<pk>/submit-review
 */
export const submitReview: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, loading) => {
  return post(
    `${buildPrefix(workspaceId)}/${id}/submit-review`,
    undefined,
    undefined,
    loading,
  )
}

/**
 * POST /finance/workspace/<wid>/materials-task/<pk>/review
 */
export const reviewTask: (
  workspaceId: string,
  id: string,
  body: MaterialsTaskReviewBody,
  loading?: Ref<boolean>,
) => Promise<Result<MaterialsTask>> = (workspaceId, id, body, loading) => {
  return post(`${buildPrefix(workspaceId)}/${id}/review`, body, undefined, loading)
}

/**
 * GET /finance/workspace/<wid>/materials-task/<pk>/zip
 * Streams a zip; the shared `exportFile` helper extracts the filename from
 * `Content-Disposition` and triggers the browser save dialog.
 */
export const downloadZip: (
  workspaceId: string,
  id: string,
  fallbackName: string,
  loading?: Ref<boolean>,
) => Promise<unknown> = (workspaceId, id, fallbackName, loading) => {
  return exportFile(
    fallbackName,
    `${buildPrefix(workspaceId)}/${id}/zip`,
    undefined,
    loading,
  )
}

export default {
  listTasks,
  getTask,
  createTask,
  updateTask,
  deleteTask,
  parseRequirements,
  matchDocuments,
  updateSelection,
  summarize,
  packZip,
  submitReview,
  reviewTask,
  downloadZip,
}

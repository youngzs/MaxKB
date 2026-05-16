import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { del, exportFile, get, post, put } from '@/request/index'
import type {
  PageResult,
  Template,
  TemplateListParams,
  TemplateUpdate,
} from './type'

/**
 * Finance template API client (Gate 3 Track C).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/template`
 * The axios instance already prefixes `/admin/api`, so paths here start with `/finance/...`.
 */

const buildPrefix = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/template`

/**
 * GET /finance/workspace/<wid>/template?scenario=&page=&size=
 */
export const listTemplates: (
  workspaceId: string,
  params?: TemplateListParams,
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<Template>>> = (workspaceId, params, loading) => {
  return get(`${buildPrefix(workspaceId)}`, params, loading)
}

/**
 * GET /finance/workspace/<wid>/template/<pk>
 */
export const getTemplate: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<Template>> = (workspaceId, id, loading) => {
  return get(`${buildPrefix(workspaceId)}/${id}`, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/template (multipart/form-data)
 * Body: file (docx) + name + scenario.
 * The shared `post()` helper hands `FormData` straight to axios which sets
 * the `Content-Type` header (with boundary) automatically.
 */
export const uploadTemplate: (
  workspaceId: string,
  file: File,
  name: string,
  scenario: string,
  loading?: Ref<boolean>,
) => Promise<Result<Template>> = (workspaceId, file, name, scenario, loading) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('name', name)
  fd.append('scenario', scenario)
  return post(`${buildPrefix(workspaceId)}`, fd, undefined, loading)
}

/**
 * PUT /finance/workspace/<wid>/template/<pk>
 */
export const updateTemplate: (
  workspaceId: string,
  id: string,
  body: TemplateUpdate,
  loading?: Ref<boolean>,
) => Promise<Result<Template>> = (workspaceId, id, body, loading) => {
  return put(`${buildPrefix(workspaceId)}/${id}`, body, undefined, loading)
}

/**
 * DELETE /finance/workspace/<wid>/template/<pk>
 */
export const deleteTemplate: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<null>> = (workspaceId, id, loading) => {
  return del(`${buildPrefix(workspaceId)}/${id}`, undefined, {}, loading)
}

/**
 * GET /finance/workspace/<wid>/template/sample
 * Streams a freshly-built sample .docx demonstrating placeholder syntax.
 * Uses the shared `exportFile` helper so backend JSON errors still surface
 * via MsgError instead of corrupting the saved blob.
 */
export const downloadSampleTemplate: (
  workspaceId: string,
  fallbackFilename?: string,
  loading?: Ref<boolean>,
) => Promise<boolean> = (
  workspaceId,
  fallbackFilename = 'finance-template-sample.docx',
  loading,
) => {
  return exportFile(
    fallbackFilename,
    `${buildPrefix(workspaceId)}/sample`,
    undefined,
    loading,
  )
}

/**
 * GET /finance/workspace/<wid>/template/<pk>/download
 * Streams the previously uploaded .docx so users can edit + reupload.
 */
export const downloadTemplate: (
  workspaceId: string,
  id: string,
  fallbackFilename?: string,
  loading?: Ref<boolean>,
) => Promise<boolean> = (
  workspaceId,
  id,
  fallbackFilename = 'template.docx',
  loading,
) => {
  return exportFile(
    fallbackFilename,
    `${buildPrefix(workspaceId)}/${id}/download`,
    undefined,
    loading,
  )
}

export default {
  listTemplates,
  getTemplate,
  uploadTemplate,
  updateTemplate,
  deleteTemplate,
  downloadSampleTemplate,
  downloadTemplate,
}

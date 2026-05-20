import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get, post, put, del } from '@/request/index'
import type {
  ListParams,
  PageResult,
  Project,
  ProjectInput,
  StageTemplatesMap,
} from './type'

/**
 * Finance project API client.
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/project`
 * The axios instance already prefixes `/admin/api`, so paths here start with `/finance/...`.
 */

const buildPrefix = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/project`

/**
 * GET /finance/workspace/<wid>/project/?keyword=&status=&page=&size=
 */
export const listProjects: (
  workspaceId: string,
  params?: ListParams,
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<Project>>> = (workspaceId, params, loading) => {
  return get(`${buildPrefix(workspaceId)}`, params, loading)
}

/**
 * GET /finance/workspace/<wid>/project/<pk>
 */
export const getProject: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<Project>> = (workspaceId, id, loading) => {
  return get(`${buildPrefix(workspaceId)}/${id}`, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/project/
 */
export const createProject: (
  workspaceId: string,
  body: ProjectInput,
  loading?: Ref<boolean>,
) => Promise<Result<Project>> = (workspaceId, body, loading) => {
  return post(`${buildPrefix(workspaceId)}`, body, undefined, loading)
}

/**
 * PUT /finance/workspace/<wid>/project/<pk>
 */
export const updateProject: (
  workspaceId: string,
  id: string,
  body: ProjectInput,
  loading?: Ref<boolean>,
) => Promise<Result<Project>> = (workspaceId, id, body, loading) => {
  return put(`${buildPrefix(workspaceId)}/${id}`, body, undefined, loading)
}

/**
 * DELETE /finance/workspace/<wid>/project/<pk>
 */
export const deleteProject: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<null>> = (workspaceId, id, loading) => {
  return del(`${buildPrefix(workspaceId)}/${id}`, undefined, {}, loading)
}

/**
 * GET /finance/workspace/<wid>/stage-templates
 * 五套 project_type 阶段模板 —— 创建项目表单按所选类型列出阶段。
 */
export const getStageTemplates: (
  workspaceId: string,
  loading?: Ref<boolean>,
) => Promise<Result<StageTemplatesMap>> = (workspaceId, loading) => {
  return get(`/finance/workspace/${workspaceId}/stage-templates`, undefined, loading)
}

export default {
  listProjects,
  getProject,
  createProject,
  updateProject,
  deleteProject,
  getStageTemplates,
}

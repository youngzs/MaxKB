import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get, post, put } from '@/request/index'
import type {
  AlertsResponse,
  DashboardData,
  GanttParams,
  GanttResponse,
  Project,
  StageRecord,
  StageUpdateInput,
} from './type'

/**
 * Finance progress (P2 进度归集) API client.
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/...`
 * The axios instance already prefixes `/admin/api`.
 */

const wsPrefix = (workspaceId: string) => `/finance/workspace/${workspaceId}`

/**
 * GET /finance/workspace/<wid>/progress/gantt — 项目列表 + 各项目阶段记录。
 */
export const getGanttData: (
  workspaceId: string,
  params?: GanttParams,
  loading?: Ref<boolean>,
) => Promise<Result<GanttResponse>> = (workspaceId, params, loading) => {
  return get(`${wsPrefix(workspaceId)}/progress/gantt`, params, loading)
}

/**
 * GET /finance/workspace/<wid>/project/<pk>/stages — 单项目全部阶段记录。
 */
export const getProjectStages: (
  workspaceId: string,
  projectId: string,
  loading?: Ref<boolean>,
) => Promise<Result<StageRecord[]>> = (workspaceId, projectId, loading) => {
  return get(`${wsPrefix(workspaceId)}/project/${projectId}/stages`, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/project/<pk>/advance — 推进到下一阶段。
 */
export const advanceStage: (
  workspaceId: string,
  projectId: string,
  note?: string,
  loading?: Ref<boolean>,
) => Promise<Result<Project>> = (workspaceId, projectId, note, loading) => {
  return post(
    `${wsPrefix(workspaceId)}/project/${projectId}/advance`,
    { note: note || '' },
    undefined,
    loading,
  )
}

/**
 * POST /finance/workspace/<wid>/project/<pk>/rollback — 回退到上一阶段。
 */
export const rollbackStage: (
  workspaceId: string,
  projectId: string,
  note?: string,
  loading?: Ref<boolean>,
) => Promise<Result<Project>> = (workspaceId, projectId, note, loading) => {
  return post(
    `${wsPrefix(workspaceId)}/project/${projectId}/rollback`,
    { note: note || '' },
    undefined,
    loading,
  )
}

/**
 * PUT /finance/workspace/<wid>/project/<pk>/stages/<stage_key> — 改单个阶段。
 */
export const updateStage: (
  workspaceId: string,
  projectId: string,
  stageKey: string,
  body: StageUpdateInput,
  loading?: Ref<boolean>,
) => Promise<Result<StageRecord>> = (workspaceId, projectId, stageKey, body, loading) => {
  return put(
    `${wsPrefix(workspaceId)}/project/${projectId}/stages/${stageKey}`,
    body,
    undefined,
    loading,
  )
}

/**
 * GET /finance/workspace/<wid>/progress/dashboard — 驾驶舱聚合 KPI。
 */
export const getDashboard: (
  workspaceId: string,
  loading?: Ref<boolean>,
) => Promise<Result<DashboardData>> = (workspaceId, loading) => {
  return get(`${wsPrefix(workspaceId)}/progress/dashboard`, undefined, loading)
}

/**
 * GET /finance/workspace/<wid>/progress/alerts — 当前风险项列表。
 */
export const getAlerts: (
  workspaceId: string,
  loading?: Ref<boolean>,
) => Promise<Result<AlertsResponse>> = (workspaceId, loading) => {
  return get(`${wsPrefix(workspaceId)}/progress/alerts`, undefined, loading)
}

export default {
  getGanttData,
  getProjectStages,
  advanceStage,
  rollbackStage,
  updateStage,
  getDashboard,
  getAlerts,
}

import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get, post } from '@/request/index'
import type { PageResult } from './type'

/**
 * Finance workflow-run API client (Gate 7 Track B).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/workflow-run`.
 *
 * One row per Celery task invocation: parse / match / pack / generate.
 * Used by the per-step progress drawer in materials/detail and the
 * documents wizard to surface real-time runtime status, retry counts,
 * and error messages.
 */

export type WorkflowRunStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'retrying'
  | 'cancelled'

export type WorkflowRunTargetType =
  | 'MATERIALS_TASK'
  | 'DOC_GENERATION'
  | 'OTHER'

export interface WorkflowRun {
  id: string
  workspace_id: string
  target_type: WorkflowRunTargetType
  target_id: string
  task_name: string
  celery_task_id: string
  status: WorkflowRunStatus
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  error_message: string
  payload: Record<string, unknown>
  retry_count: number
  created_at: string | null
  updated_at: string | null
}

export interface WorkflowRunListParams {
  target_type?: WorkflowRunTargetType
  target_id?: string
  status?: WorkflowRunStatus
  page?: number
  size?: number
}

const buildUrl = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/workflow-run`

/**
 * GET /finance/workspace/<wid>/workflow-run?target_type=&target_id=&status=&page=&size=
 */
export const listWorkflowRuns: (
  workspaceId: string,
  params?: WorkflowRunListParams,
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<WorkflowRun>>> = (
  workspaceId,
  params,
  loading,
) => {
  return get(buildUrl(workspaceId), params, loading)
}

/** Result of a retry: the original run id + the freshly-queued run. */
export interface WorkflowRunRetryResult {
  retried_from: string
  new_run: WorkflowRun | null
}

/**
 * POST /finance/workspace/<wid>/workflow-run/<id>/retry
 * Re-dispatches a failed/cancelled run as a NEW WorkflowRun row.
 */
export const retryWorkflowRun: (
  workspaceId: string,
  runId: string,
  loading?: Ref<boolean>,
) => Promise<Result<WorkflowRunRetryResult>> = (
  workspaceId,
  runId,
  loading,
) => {
  return post(`${buildUrl(workspaceId)}/${runId}/retry`, undefined, undefined, loading)
}

/**
 * POST /finance/workspace/<wid>/workflow-run/<id>/cancel
 * Revokes a queued/running/retrying run and fails the underlying target.
 */
export const cancelWorkflowRun: (
  workspaceId: string,
  runId: string,
  loading?: Ref<boolean>,
) => Promise<Result<WorkflowRun>> = (workspaceId, runId, loading) => {
  return post(`${buildUrl(workspaceId)}/${runId}/cancel`, undefined, undefined, loading)
}

export default {
  listWorkflowRuns,
  retryWorkflowRun,
  cancelWorkflowRun,
}

import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { exportFile, get } from '@/request/index'
import type { AuditLogEntry, AuditLogListParams, PageResult } from './type'

/**
 * Finance audit-log API client (Gate 5 Track C).
 *
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/audit-log`.
 * The axios instance already prefixes `/admin/api`, so paths here start
 * with `/finance/...`.
 *
 * Permission contract: the endpoint is gated on FINANCE_REVIEW or
 * WORKSPACE_MANAGE — list usage outside an admin/reviewer context will
 * 403 at the backend.
 */
const buildUrl = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/audit-log`

/**
 * GET /finance/workspace/<wid>/audit-log?target_type=&action=&actor_id=&page=&size=
 */
export const listAuditLog: (
  workspaceId: string,
  params?: AuditLogListParams,
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<AuditLogEntry>>> = (
  workspaceId,
  params,
  loading,
) => {
  return get(buildUrl(workspaceId), params, loading)
}

/**
 * GET .../audit-log?format=csv with the same filter shape as `listAuditLog`.
 *
 * Uses the standard `exportFile` helper which:
 *   1. requests a blob and routes auth headers through the axios instance,
 *   2. surfaces server-side JSON errors via MsgError, and
 *   3. triggers a synthetic <a download> click to save the file.
 *
 * `fallbackFilename` is used when the response carries no Content-Disposition;
 * the backend should set one with a date stamp.
 */
export const exportAuditLog: (
  workspaceId: string,
  params?: AuditLogListParams,
  fallbackFilename?: string,
  loading?: Ref<boolean>,
) => Promise<boolean> = (
  workspaceId,
  params,
  fallbackFilename = 'audit-log.csv',
  loading,
) => {
  return exportFile(
    fallbackFilename,
    buildUrl(workspaceId),
    { ...(params || {}), format: 'csv' },
    loading,
  )
}

export default {
  listAuditLog,
  exportAuditLog,
}

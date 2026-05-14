import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get } from '@/request/index'
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

export default {
  listAuditLog,
}

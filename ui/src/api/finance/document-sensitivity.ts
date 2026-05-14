import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { put } from '@/request/index'
import type { SensitivityLevel } from './type'

/**
 * Finance knowledge-document sensitivity API (Gate 6 Track B).
 *
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/document-sensitivity/<doc_id>`.
 * The axios instance already prefixes `/admin/api`, so paths here start
 * with `/finance/...`.
 *
 * Permission contract: gated on FINANCE_TEMPLATE_MANAGE (i.e. finance
 * managers can change the sensitivity tag on any knowledge document
 * visible inside the workspace). Non-managers receive 403 from the
 * backend; the popover wrapper short-circuits before that.
 */
const buildUrl = (workspaceId: string, docId: string) =>
  `/finance/workspace/${workspaceId}/document-sensitivity/${docId}`

export interface UpdateSensitivityBody {
  sensitivity_level: SensitivityLevel
}

export interface UpdateSensitivityResult {
  document_id: string
  sensitivity_level: SensitivityLevel
}

/**
 * PATCH-equivalent (the backend accepts PUT) — replace the sensitivity tag
 * for a single knowledge document.
 */
export const updateDocumentSensitivity: (
  workspaceId: string,
  docId: string,
  body: UpdateSensitivityBody,
  loading?: Ref<boolean>,
) => Promise<Result<UpdateSensitivityResult>> = (
  workspaceId,
  docId,
  body,
  loading,
) => {
  return put(buildUrl(workspaceId, docId), body, undefined, loading)
}

export default {
  updateDocumentSensitivity,
}

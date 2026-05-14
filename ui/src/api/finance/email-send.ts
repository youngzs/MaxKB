import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get, post } from '@/request/index'
import type {
  EmailSendLog,
  EmailSendLogListParams,
  MaterialsTaskSendBody,
  PageResult,
} from './type'

/**
 * Finance send-pipeline API client (Gate 5 Track B).
 *   POST  /materials-task/<pk>/send       — deliver the materials zip
 *   GET   /email-send-log                  — read-only audit list
 */

const baseFinance = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}`

export const sendMaterialsTask: (
  workspaceId: string,
  id: string,
  body: MaterialsTaskSendBody,
  loading?: Ref<boolean>,
) => Promise<Result<EmailSendLog>> = (workspaceId, id, body, loading) => {
  return post(
    `${baseFinance(workspaceId)}/materials-task/${id}/send`,
    body,
    undefined,
    loading,
  )
}

export const listEmailSendLogs: (
  workspaceId: string,
  params?: EmailSendLogListParams,
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<EmailSendLog>>> = (workspaceId, params, loading) => {
  return get(`${baseFinance(workspaceId)}/email-send-log`, params, loading)
}

export default {
  sendMaterialsTask,
  listEmailSendLogs,
}

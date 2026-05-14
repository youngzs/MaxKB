import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get, post, put, del } from '@/request/index'
import type {
  PageResult,
  SmtpConfig,
  SmtpConfigCreate,
  SmtpConfigUpdate,
  SmtpTestRequest,
  SmtpTestResponse,
} from './type'

/**
 * Finance SMTP-config API client (Gate 5 Track B).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/smtp-config`.
 */

const buildPrefix = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/smtp-config`

export const listSmtpConfigs: (
  workspaceId: string,
  params?: { keyword?: string; page?: number; size?: number },
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<SmtpConfig>>> = (workspaceId, params, loading) => {
  return get(`${buildPrefix(workspaceId)}`, params, loading)
}

export const getSmtpConfig: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<SmtpConfig>> = (workspaceId, id, loading) => {
  return get(`${buildPrefix(workspaceId)}/${id}`, undefined, loading)
}

export const createSmtpConfig: (
  workspaceId: string,
  body: SmtpConfigCreate,
  loading?: Ref<boolean>,
) => Promise<Result<SmtpConfig>> = (workspaceId, body, loading) => {
  return post(`${buildPrefix(workspaceId)}`, body, undefined, loading)
}

export const updateSmtpConfig: (
  workspaceId: string,
  id: string,
  body: SmtpConfigUpdate,
  loading?: Ref<boolean>,
) => Promise<Result<SmtpConfig>> = (workspaceId, id, body, loading) => {
  return put(`${buildPrefix(workspaceId)}/${id}`, body, undefined, loading)
}

export const deleteSmtpConfig: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<null>> = (workspaceId, id, loading) => {
  return del(`${buildPrefix(workspaceId)}/${id}`, undefined, {}, loading)
}

export const testSmtpConfig: (
  workspaceId: string,
  id: string,
  body: SmtpTestRequest,
  loading?: Ref<boolean>,
) => Promise<Result<SmtpTestResponse>> = (workspaceId, id, body, loading) => {
  return post(`${buildPrefix(workspaceId)}/${id}/test`, body, undefined, loading)
}

export default {
  listSmtpConfigs,
  getSmtpConfig,
  createSmtpConfig,
  updateSmtpConfig,
  deleteSmtpConfig,
  testSmtpConfig,
}

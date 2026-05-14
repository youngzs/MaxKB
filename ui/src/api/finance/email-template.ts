import { type Ref } from 'vue'
import type { Result } from '@/request/Result'
import { get, post, put, del } from '@/request/index'
import type {
  EmailTemplate,
  EmailTemplateCreate,
  EmailTemplateScenario,
  EmailTemplateUpdate,
  PageResult,
} from './type'

/**
 * Finance email-template API client (Gate 5 Track B).
 * Backend mount: `/admin/api/finance/workspace/<workspace_id>/email-template`.
 */

const buildPrefix = (workspaceId: string) =>
  `/finance/workspace/${workspaceId}/email-template`

export const listEmailTemplates: (
  workspaceId: string,
  params?: {
    scenario?: EmailTemplateScenario | ''
    keyword?: string
    page?: number
    size?: number
  },
  loading?: Ref<boolean>,
) => Promise<Result<PageResult<EmailTemplate>>> = (workspaceId, params, loading) => {
  return get(`${buildPrefix(workspaceId)}`, params, loading)
}

export const getEmailTemplate: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<EmailTemplate>> = (workspaceId, id, loading) => {
  return get(`${buildPrefix(workspaceId)}/${id}`, undefined, loading)
}

export const createEmailTemplate: (
  workspaceId: string,
  body: EmailTemplateCreate,
  loading?: Ref<boolean>,
) => Promise<Result<EmailTemplate>> = (workspaceId, body, loading) => {
  return post(`${buildPrefix(workspaceId)}`, body, undefined, loading)
}

export const updateEmailTemplate: (
  workspaceId: string,
  id: string,
  body: EmailTemplateUpdate,
  loading?: Ref<boolean>,
) => Promise<Result<EmailTemplate>> = (workspaceId, id, body, loading) => {
  return put(`${buildPrefix(workspaceId)}/${id}`, body, undefined, loading)
}

export const deleteEmailTemplate: (
  workspaceId: string,
  id: string,
  loading?: Ref<boolean>,
) => Promise<Result<null>> = (workspaceId, id, loading) => {
  return del(`${buildPrefix(workspaceId)}/${id}`, undefined, {}, loading)
}

export default {
  listEmailTemplates,
  getEmailTemplate,
  createEmailTemplate,
  updateEmailTemplate,
  deleteEmailTemplate,
}

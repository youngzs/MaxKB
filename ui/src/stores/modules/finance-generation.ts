import { defineStore } from 'pinia'
import {
  listGenerations,
  getGeneration,
  createGeneration,
  confirmGeneration,
  revokeGeneration,
  fetchPreview,
  downloadGeneration,
  aiFillPlaceholders,
} from '@/api/finance/generation'
import type {
  AIFillResponse,
  Generation,
  GenerationCreate,
  GenerationStatus,
} from '@/api/finance/type'

export interface FinanceGenerationState {
  list: Generation[]
  total: number
  currentPage: number
  pageSize: number
  projectFilter: string
  statusFilter: '' | GenerationStatus
  loading: boolean
  selected: Generation | null
  previewHtml: string
  previewLoading: boolean
}

const useFinanceGenerationStore = defineStore('finance-generation', {
  state: (): FinanceGenerationState => ({
    list: [],
    total: 0,
    currentPage: 1,
    pageSize: 20,
    projectFilter: '',
    statusFilter: '',
    loading: false,
    selected: null,
    previewHtml: '',
    previewLoading: false,
  }),
  actions: {
    async fetchList(workspaceId: string) {
      this.loading = true
      try {
        const params = {
          project_id: this.projectFilter || undefined,
          status: this.statusFilter || undefined,
          page: this.currentPage,
          size: this.pageSize,
        }
        const res = await listGenerations(workspaceId, params)
        const data = res?.data
        if (data) {
          this.list = data.records || []
          this.total = data.total || 0
        } else {
          this.list = []
          this.total = 0
        }
      } finally {
        this.loading = false
      }
    },
    async fetchDetail(workspaceId: string, id: string) {
      const res = await getGeneration(workspaceId, id)
      this.selected = res?.data ?? null
      return this.selected
    },
    async create(workspaceId: string, body: GenerationCreate) {
      const res = await createGeneration(workspaceId, body)
      const created = res?.data
      if (created) {
        this.list = [created, ...this.list]
        this.total += 1
      }
      return created
    },
    async confirm(workspaceId: string, id: string) {
      const res = await confirmGeneration(workspaceId, id)
      const updated = res?.data
      this.applyUpdate(id, updated)
      return updated
    },
    async revoke(workspaceId: string, id: string) {
      const res = await revokeGeneration(workspaceId, id)
      const updated = res?.data
      this.applyUpdate(id, updated)
      return updated
    },
    applyUpdate(id: string, updated: Generation | undefined) {
      if (!updated) return
      const idx = this.list.findIndex((item) => item.id === id)
      if (idx >= 0) {
        this.list.splice(idx, 1, updated)
      }
      if (this.selected && this.selected.id === id) {
        this.selected = updated
      }
    },
    async fetchPreview(workspaceId: string, id: string) {
      this.previewLoading = true
      try {
        const res = await fetchPreview(workspaceId, id)
        this.previewHtml = res?.data?.html ?? ''
        return this.previewHtml
      } finally {
        this.previewLoading = false
      }
    },
    async download(workspaceId: string, id: string, fallbackName: string) {
      await downloadGeneration(workspaceId, id, fallbackName)
    },
    async aiFill(
      workspaceId: string,
      templateId: string,
      projectId: string,
      placeholderKeys: string[],
    ): Promise<AIFillResponse> {
      if (placeholderKeys.length === 0) return {}
      const res = await aiFillPlaceholders(workspaceId, {
        template_id: templateId,
        project_id: projectId,
        placeholder_keys: placeholderKeys,
      })
      return res?.data ?? {}
    },
    setProjectFilter(projectId: string) {
      this.projectFilter = projectId
      this.currentPage = 1
    },
    setStatusFilter(status: '' | GenerationStatus) {
      this.statusFilter = status
      this.currentPage = 1
    },
    setPage(page: number) {
      this.currentPage = page
    },
    setPageSize(size: number) {
      this.pageSize = size
      this.currentPage = 1
    },
    resetFilters() {
      this.projectFilter = ''
      this.statusFilter = ''
      this.currentPage = 1
    },
    clearPreview() {
      this.previewHtml = ''
    },
  },
})

export default useFinanceGenerationStore

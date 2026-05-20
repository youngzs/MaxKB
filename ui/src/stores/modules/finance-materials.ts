import { defineStore } from 'pinia'
import {
  listTasks,
  getTask,
  createTask,
  updateTask,
  deleteTask,
  parseRequirements,
  matchDocuments,
  updateSelection,
  summarize,
  packZip,
  submitReview,
  reviewTask,
} from '@/api/finance/materials-task'
import type {
  MaterialsTask,
  MaterialsTaskStatus,
  MaterialsTaskSelectionUpdate,
  MaterialsTaskReviewBody,
} from '@/api/finance/type'

/**
 * Statuses that represent async server-side work — when a task is in one of these
 * we should poll until it settles.
 */
const TRANSIENT_STATUSES: MaterialsTaskStatus[] = ['parsing', 'matching']

const isTransient = (s: MaterialsTaskStatus) => TRANSIENT_STATUSES.includes(s)

export interface FinanceMaterialsState {
  list: MaterialsTask[]
  total: number
  currentPage: number
  pageSize: number
  projectFilter: string
  statusFilter: '' | MaterialsTaskStatus
  loading: boolean
  selected: MaterialsTask | null
  /** Active polling task ids (keys are task ids). */
  polling: Record<string, boolean>
}

const useFinanceMaterialsStore = defineStore('finance-materials', {
  state: (): FinanceMaterialsState => ({
    list: [],
    total: 0,
    currentPage: 1,
    pageSize: 20,
    projectFilter: '',
    statusFilter: '',
    loading: false,
    selected: null,
    polling: {},
  }),
  getters: {
    hasTransientInList(state): boolean {
      return state.list.some((t) => isTransient(t.status))
    },
  },
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
        const res = await listTasks(workspaceId, params)
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
    /** Silent refresh — used by the auto-poll timer; doesn't toggle `loading`. */
    async refreshListSilent(workspaceId: string) {
      const params = {
        project_id: this.projectFilter || undefined,
        status: this.statusFilter || undefined,
        page: this.currentPage,
        size: this.pageSize,
      }
      const res = await listTasks(workspaceId, params)
      const data = res?.data
      if (data) {
        this.list = data.records || []
        this.total = data.total || 0
      }
    },
    async fetchDetail(workspaceId: string, id: string) {
      const res = await getTask(workspaceId, id)
      this.selected = res?.data ?? null
      return this.selected
    },
    async create(
      workspaceId: string,
      body: {
        project_id: string
        title: string
        requirement_text?: string
        file?: File
      },
    ) {
      const res = await createTask(workspaceId, body)
      const created = res?.data
      if (created) {
        this.list = [created, ...this.list]
        this.total += 1
      }
      return created
    },
    /**
     * Partial update of an editable task (DRAFT / FAILED / PARSING / MATCHING).
     * Returns the refreshed task; also syncs `selected` and the list cache.
     */
    async update(
      workspaceId: string,
      id: string,
      body: {
        title?: string
        requirement_text?: string
        parsed_items?: Array<{
          key: string
          label: string
          description?: string
          required?: boolean
        }>
      },
    ) {
      const res = await updateTask(workspaceId, id, body)
      const updated = res?.data
      if (updated) {
        if (this.selected && this.selected.id === id) {
          this.selected = updated
        }
        const idx = this.list.findIndex((it) => it.id === id)
        if (idx >= 0) this.list.splice(idx, 1, updated)
      }
      return updated
    },
    async remove(workspaceId: string, id: string) {
      await deleteTask(workspaceId, id)
      const idx = this.list.findIndex((item) => item.id === id)
      if (idx >= 0) {
        this.list.splice(idx, 1)
        this.total = Math.max(0, this.total - 1)
      }
      if (this.selected && this.selected.id === id) {
        this.selected = null
      }
    },
    /** Replace the in-store representation (list + selected) with a freshly
     *  returned MaterialsTask. */
    upsert(task: MaterialsTask) {
      const idx = this.list.findIndex((t) => t.id === task.id)
      if (idx >= 0) {
        this.list.splice(idx, 1, task)
      }
      if (this.selected && this.selected.id === task.id) {
        this.selected = task
      }
    },
    async triggerParse(workspaceId: string, id: string) {
      const res = await parseRequirements(workspaceId, id)
      if (res?.data) this.upsert(res.data)
      return res?.data
    },
    async triggerMatch(workspaceId: string, id: string) {
      const res = await matchDocuments(workspaceId, id)
      if (res?.data) this.upsert(res.data)
      return res?.data
    },
    async saveSelection(
      workspaceId: string,
      id: string,
      body: MaterialsTaskSelectionUpdate,
    ) {
      const res = await updateSelection(workspaceId, id, body)
      if (res?.data) this.upsert(res.data)
      return res?.data
    },
    async triggerSummarize(workspaceId: string, id: string) {
      const res = await summarize(workspaceId, id)
      if (res?.data) this.upsert(res.data)
      return res?.data
    },
    async triggerPack(workspaceId: string, id: string) {
      const res = await packZip(workspaceId, id)
      if (res?.data) this.upsert(res.data)
      return res?.data
    },
    async triggerSubmitReview(workspaceId: string, id: string) {
      const res = await submitReview(workspaceId, id)
      if (res?.data) this.upsert(res.data)
      return res?.data
    },
    async triggerReview(
      workspaceId: string,
      id: string,
      body: MaterialsTaskReviewBody,
    ) {
      const res = await reviewTask(workspaceId, id, body)
      if (res?.data) this.upsert(res.data)
      return res?.data
    },
    /**
     * Poll GET <task> every 3 seconds while its status is `parsing` or `matching`.
     * Stops on any other status or after `timeoutMs` (default 60 s).
     * Returns the final task on success or null on timeout / not-found.
     */
    async pollUntilStatusStable(
      workspaceId: string,
      id: string,
      timeoutMs = 60000,
    ): Promise<MaterialsTask | null> {
      this.polling[id] = true
      const start = Date.now()
      const intervalMs = 3000
      try {
        // First fetch — bail immediately if already stable.
        let current = await this.fetchDetail(workspaceId, id)
        if (!current || !isTransient(current.status)) return current
        while (Date.now() - start < timeoutMs) {
          await new Promise((r) => setTimeout(r, intervalMs))
          // Caller may have navigated away — bail out cooperatively.
          if (!this.polling[id]) return current
          current = await this.fetchDetail(workspaceId, id)
          if (!current) return null
          if (!isTransient(current.status)) return current
        }
        return current
      } finally {
        delete this.polling[id]
      }
    },
    stopPolling(id: string) {
      delete this.polling[id]
    },
    setProjectFilter(projectId: string) {
      this.projectFilter = projectId
      this.currentPage = 1
    },
    setStatusFilter(status: '' | MaterialsTaskStatus) {
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
  },
})

export default useFinanceMaterialsStore

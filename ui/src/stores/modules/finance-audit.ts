import { defineStore } from 'pinia'
import { listAuditLog } from '@/api/finance/audit-log'
import type {
  AuditAction,
  AuditLogEntry,
  AuditTargetType,
} from '@/api/finance/type'

/**
 * Finance audit-log store (Gate 5 Track C).
 *
 * Read-only: there is no write surface — audit rows are produced server-side
 * by the audit_log decorator. The store keeps filters, pagination, and a
 * cached page of rows; refetch is driven by the view.
 */
export interface FinanceAuditFilters {
  targetType: '' | AuditTargetType
  action: '' | AuditAction
  actorId: string
  targetId: string
  /** ISO datetime — inclusive lower bound. */
  dateFrom: string
  /** ISO datetime — exclusive upper bound. */
  dateTo: string
  keyword: string
}

export interface FinanceAuditState {
  list: AuditLogEntry[]
  total: number
  currentPage: number
  pageSize: number
  loading: boolean
  filters: FinanceAuditFilters
}

const defaultFilters = (): FinanceAuditFilters => ({
  targetType: '',
  action: '',
  actorId: '',
  targetId: '',
  dateFrom: '',
  dateTo: '',
  keyword: '',
})

const useFinanceAuditStore = defineStore('finance-audit', {
  state: (): FinanceAuditState => ({
    list: [],
    total: 0,
    currentPage: 1,
    pageSize: 20,
    loading: false,
    filters: defaultFilters(),
  }),
  actions: {
    async fetchList(workspaceId: string) {
      this.loading = true
      try {
        const f = this.filters
        const params = {
          target_type: f.targetType || undefined,
          action: f.action || undefined,
          actor_id: f.actorId || undefined,
          target_id: f.targetId || undefined,
          date_from: f.dateFrom || undefined,
          date_to: f.dateTo || undefined,
          keyword: f.keyword || undefined,
          page: this.currentPage,
          size: this.pageSize,
        }
        const res = await listAuditLog(workspaceId, params)
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
    setFilter<K extends keyof FinanceAuditFilters>(
      key: K,
      value: FinanceAuditFilters[K],
    ) {
      this.filters[key] = value
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
      this.filters = defaultFilters()
      this.currentPage = 1
    },
  },
})

export default useFinanceAuditStore

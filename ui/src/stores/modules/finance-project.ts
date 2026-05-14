import { defineStore } from 'pinia'
import {
  listProjects,
  getProject,
  createProject,
  updateProject,
  deleteProject,
} from '@/api/finance/project'
import type { Project, ProjectInput, ProjectStatus } from '@/api/finance/type'

export interface FinanceProjectState {
  list: Project[]
  total: number
  currentPage: number
  pageSize: number
  keyword: string
  statusFilter: '' | ProjectStatus
  loading: boolean
  selected: Project | null
}

const useFinanceProjectStore = defineStore('finance-project', {
  state: (): FinanceProjectState => ({
    list: [],
    total: 0,
    currentPage: 1,
    pageSize: 20,
    keyword: '',
    statusFilter: '',
    loading: false,
    selected: null,
  }),
  actions: {
    async fetchList(workspaceId: string) {
      this.loading = true
      try {
        const params = {
          keyword: this.keyword || undefined,
          status: this.statusFilter || undefined,
          page: this.currentPage,
          size: this.pageSize,
        }
        const res = await listProjects(workspaceId, params)
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
      const res = await getProject(workspaceId, id)
      this.selected = res?.data ?? null
      return this.selected
    },
    async create(workspaceId: string, body: ProjectInput) {
      const res = await createProject(workspaceId, body)
      const created = res?.data
      if (created) {
        this.list = [created, ...this.list]
        this.total += 1
      }
      return created
    },
    async update(workspaceId: string, id: string, body: ProjectInput) {
      const res = await updateProject(workspaceId, id, body)
      const updated = res?.data
      if (updated) {
        const idx = this.list.findIndex((item) => item.id === id)
        if (idx >= 0) {
          this.list.splice(idx, 1, updated)
        }
        if (this.selected && this.selected.id === id) {
          this.selected = updated
        }
      }
      return updated
    },
    async remove(workspaceId: string, id: string) {
      await deleteProject(workspaceId, id)
      const idx = this.list.findIndex((item) => item.id === id)
      if (idx >= 0) {
        this.list.splice(idx, 1)
        this.total = Math.max(0, this.total - 1)
      }
      if (this.selected && this.selected.id === id) {
        this.selected = null
      }
    },
    setKeyword(keyword: string) {
      this.keyword = keyword
      this.currentPage = 1
    },
    setStatusFilter(status: '' | ProjectStatus) {
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
      this.keyword = ''
      this.statusFilter = ''
      this.currentPage = 1
    },
  },
})

export default useFinanceProjectStore

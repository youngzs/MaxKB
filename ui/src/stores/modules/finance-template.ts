import { defineStore } from 'pinia'
import {
  listTemplates,
  getTemplate,
  uploadTemplate,
  updateTemplate,
  deleteTemplate,
} from '@/api/finance/template'
import type {
  Template,
  TemplateScenario,
  TemplateUpdate,
} from '@/api/finance/type'

export interface FinanceTemplateState {
  list: Template[]
  total: number
  currentPage: number
  pageSize: number
  scenarioFilter: '' | TemplateScenario
  loading: boolean
  selected: Template | null
}

const useFinanceTemplateStore = defineStore('finance-template', {
  state: (): FinanceTemplateState => ({
    list: [],
    total: 0,
    currentPage: 1,
    pageSize: 20,
    scenarioFilter: '',
    loading: false,
    selected: null,
  }),
  actions: {
    async fetchList(workspaceId: string) {
      this.loading = true
      try {
        const params = {
          scenario: this.scenarioFilter || undefined,
          page: this.currentPage,
          size: this.pageSize,
        }
        const res = await listTemplates(workspaceId, params)
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
      const res = await getTemplate(workspaceId, id)
      this.selected = res?.data ?? null
      return this.selected
    },
    async upload(workspaceId: string, file: File, name: string, scenario: TemplateScenario) {
      const res = await uploadTemplate(workspaceId, file, name, scenario)
      const created = res?.data
      if (created) {
        this.list = [created, ...this.list]
        this.total += 1
      }
      return created
    },
    async updateMeta(workspaceId: string, id: string, body: TemplateUpdate) {
      const res = await updateTemplate(workspaceId, id, body)
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
      await deleteTemplate(workspaceId, id)
      const idx = this.list.findIndex((item) => item.id === id)
      if (idx >= 0) {
        this.list.splice(idx, 1)
        this.total = Math.max(0, this.total - 1)
      }
      if (this.selected && this.selected.id === id) {
        this.selected = null
      }
    },
    setScenarioFilter(scenario: '' | TemplateScenario) {
      this.scenarioFilter = scenario
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
      this.scenarioFilter = ''
      this.currentPage = 1
    },
  },
})

export default useFinanceTemplateStore

<template>
  <div class="finance-audit p-24">
    <div class="finance-audit__header flex-between mb-16">
      <div>
        <h2 class="finance-audit__title">{{ $t('views.finance.audit') }}</h2>
        <p class="finance-audit__subtitle">{{ $t('views.finance.auditPage.subtitle') }}</p>
      </div>
      <div class="flex" style="gap: 8px; align-items: center">
        <!-- Celery worker health card 已移除 ——
             system-info 后端要求"用户在 *这个* workspace 是 ADMIN"，
             而前端 `RoleConst.ADMIN` 只校验系统级，两者无法精准对齐：
             system-level ADMIN 但非 workspace-level ADMIN 的账号在这里会必中 403。
             Celery 健康监控属诊断面板，应有独立的 /finance/diagnostics 入口。
             见 git history 取回的话查 c23b3e028 之前。 -->
        <el-button
          type="primary"
          plain
          :loading="exporting"
          @click="onExportCsv"
        >
          {{ $t('views.finance.auditPage.exportCsv') }}
        </el-button>
        <el-button @click="onReset">{{ $t('views.finance.auditPage.reset') }}</el-button>
      </div>
    </div>

    <!--
      响应式 grid：xl >= 6 列(对象类型/操作/操作人ID/时间范围占2列/关键词)，
      lg = 2 行 3 列，md = 2 列，sm = 1 列。inputs / selects 用 100% 宽度
      自然填满 col，不再被 inline form 横向挤压成针孔。
    -->
    <div class="finance-audit__filters mb-16">
      <el-form
        :model="filterModel"
        label-position="top"
        @submit.prevent
      >
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
            <el-form-item :label="$t('views.finance.auditPage.filters.targetType')">
              <el-select
                v-model="filterModel.targetType"
                :placeholder="$t('views.finance.auditPage.filters.allTargets')"
                clearable
                style="width: 100%"
                @change="onFilterChange('targetType', $event)"
              >
                <el-option
                  v-for="opt in targetTypeOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
            <el-form-item :label="$t('views.finance.auditPage.filters.action')">
              <el-select
                v-model="filterModel.action"
                :placeholder="$t('views.finance.auditPage.filters.allActions')"
                clearable
                style="width: 100%"
                @change="onFilterChange('action', $event)"
              >
                <el-option
                  v-for="opt in actionOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
            <el-form-item :label="$t('views.finance.auditPage.filters.actorId')">
              <el-input
                v-model="filterModel.actorId"
                :placeholder="$t('views.finance.auditPage.filters.actorIdPlaceholder')"
                clearable
                style="width: 100%"
                @change="onFilterChange('actorId', filterModel.actorId)"
                @clear="onFilterChange('actorId', '')"
              />
            </el-form-item>
          </el-col>

          <!-- datetimerange 比较宽，给它 2 倍 col 宽 -->
          <el-col :xs="24" :sm="24" :md="16" :lg="12" :xl="8">
            <el-form-item :label="$t('views.finance.auditPage.filters.dateRange')">
              <el-date-picker
                v-model="dateRange"
                type="datetimerange"
                value-format="YYYY-MM-DDTHH:mm:ss"
                :start-placeholder="$t('views.finance.auditPage.filters.dateFrom')"
                :end-placeholder="$t('views.finance.auditPage.filters.dateTo')"
                style="width: 100%"
                @change="onDateRangeChange"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :sm="24" :md="16" :lg="12" :xl="4">
            <el-form-item :label="$t('views.finance.auditPage.filters.keyword')">
              <el-input
                v-model="filterModel.keyword"
                :placeholder="$t('views.finance.auditPage.filters.keywordPlaceholder')"
                clearable
                style="width: 100%"
                @change="onFilterChange('keyword', filterModel.keyword)"
                @clear="onFilterChange('keyword', '')"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </div>

    <el-table
      v-loading="store.loading"
      :data="store.list"
      class="finance-audit__table"
      stripe
      style="width: 100%"
      empty-text=" "
      row-key="id"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="finance-audit__expand">
            <div class="finance-audit__expand-meta">
              <div>
                <span class="finance-audit__expand-label">
                  {{ $t('views.finance.auditPage.fields.userAgent') }}
                </span>
                <span class="finance-audit__expand-value">{{ row.user_agent || '-' }}</span>
              </div>
              <div>
                <span class="finance-audit__expand-label">
                  {{ $t('views.finance.auditPage.fields.targetId') }}
                </span>
                <span class="finance-audit__expand-value">{{ row.target_id || '-' }}</span>
              </div>
            </div>
            <JsonPayload :value="row.payload" max-height="320px" class="finance-audit__payload" />
            <div class="finance-audit__expand-actions">
              <el-button size="small" @click="openPayloadDialog(row)">
                {{ $t('views.finance.auditPage.actions.viewPayload') }}
              </el-button>
            </div>
          </div>
        </template>
      </el-table-column>

      <el-table-column
        :label="$t('views.finance.auditPage.columns.time')"
        min-width="170"
      >
        <template #default="{ row }">
          <span>{{ formatDate(row.created_at) }}</span>
        </template>
      </el-table-column>

      <el-table-column
        prop="actor_id"
        :label="$t('views.finance.auditPage.columns.actor')"
        min-width="160"
      >
        <template #default="{ row }">
          <span class="finance-audit__mono">{{ shortId(row.actor_id) }}</span>
        </template>
      </el-table-column>

      <el-table-column
        :label="$t('views.finance.auditPage.columns.action')"
        min-width="120"
      >
        <template #default="{ row }">
          <el-tag :type="actionTagType(row.action)" disable-transitions size="small">
            {{ actionLabel(row.action) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column
        :label="$t('views.finance.auditPage.columns.targetType')"
        min-width="140"
      >
        <template #default="{ row }">
          {{ targetTypeLabel(row.target_type) }}
        </template>
      </el-table-column>

      <el-table-column
        :label="$t('views.finance.auditPage.columns.targetIdShort')"
        min-width="120"
      >
        <template #default="{ row }">
          <span class="finance-audit__mono">{{ shortId(row.target_id) }}</span>
        </template>
      </el-table-column>

      <el-table-column
        prop="ip"
        :label="$t('views.finance.auditPage.columns.ip')"
        min-width="130"
      >
        <template #default="{ row }">
          <span class="finance-audit__mono">{{ row.ip || '-' }}</span>
        </template>
      </el-table-column>

      <el-table-column
        :label="$t('views.finance.auditPage.columns.payload')"
        width="120"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openPayloadDialog(row)">
            {{ $t('views.finance.auditPage.actions.viewPayload') }}
          </el-button>
        </template>
      </el-table-column>

      <template #empty>
        <el-empty
          v-if="!isFiltered"
          :image-size="100"
          class="finance-audit__empty"
        >
          <template #description>
            <div class="finance-empty-state">
              <h3>{{ $t('views.finance.auditPage.emptyState.title') }}</h3>
              <p class="text-secondary">{{ $t('views.finance.auditPage.emptyState.subtitle') }}</p>
            </div>
          </template>
        </el-empty>
        <div v-else class="finance-audit__empty">
          <p>{{ $t('views.finance.auditPage.emptyFiltered') }}</p>
        </div>
      </template>
    </el-table>

    <div class="finance-audit__pagination flex" v-if="store.total > 0">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="store.total"
        :page-sizes="[20, 50, 100, 200]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>

    <el-dialog
      v-model="payloadDialogVisible"
      :title="$t('views.finance.auditPage.dialog.title')"
      width="720px"
      append-to-body
    >
      <div class="finance-audit__dialog-meta" v-if="payloadDialogRow">
        <div>
          <span class="finance-audit__expand-label">
            {{ $t('views.finance.auditPage.columns.time') }}
          </span>
          {{ formatDate(payloadDialogRow.created_at) }}
        </div>
        <div>
          <span class="finance-audit__expand-label">
            {{ $t('views.finance.auditPage.columns.actor') }}
          </span>
          <span class="finance-audit__mono">{{ payloadDialogRow.actor_id }}</span>
        </div>
        <div>
          <span class="finance-audit__expand-label">
            {{ $t('views.finance.auditPage.columns.action') }}
          </span>
          {{ actionLabel(payloadDialogRow.action) }}
        </div>
        <div>
          <span class="finance-audit__expand-label">
            {{ $t('views.finance.auditPage.columns.targetType') }}
          </span>
          {{ targetTypeLabel(payloadDialogRow.target_type) }}
        </div>
        <div v-if="payloadDialogRow.target_id">
          <span class="finance-audit__expand-label">
            {{ $t('views.finance.auditPage.fields.targetId') }}
          </span>
          <span class="finance-audit__mono">{{ payloadDialogRow.target_id }}</span>
        </div>
      </div>
      <JsonPayload
        v-if="payloadDialogRow"
        :value="payloadDialogRow.payload"
        max-height="480px"
        class="finance-audit__payload--dialog"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { debounce } from 'lodash'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { RoleConst } from '@/utils/permission/data'
import { exportAuditLog } from '@/api/finance/audit-log'
import type {
  AuditAction,
  AuditLogEntry,
  AuditTargetType,
} from '@/api/finance/type'
import type { FinanceAuditFilters } from '@/stores/modules/finance-audit'
import JsonPayload from '../components/JsonPayload.vue'

const router = useRouter()
const { user, financeAudit: store } = useStore()

// Gate 用户能否打开审计页 —— ADMIN 或工作空间管理员都可以读审计日志。
// 这是 defence-in-depth：后端额外按 FINANCE_REVIEW / WORKSPACE_MANAGE 鉴权。
const isAdmin = hasPermission(
  [RoleConst.ADMIN, RoleConst.WORKSPACE_MANAGE.getWorkspaceRole],
  'OR',
)

const filterModel = reactive<FinanceAuditFilters>({ ...store.filters })

// el-date-picker emits a [string|null, string|null] tuple; null when cleared.
const dateRange = ref<[string, string] | null>(
  store.filters.dateFrom && store.filters.dateTo
    ? [store.filters.dateFrom, store.filters.dateTo]
    : null,
)

const currentPage = computed<number>({
  get: () => store.currentPage,
  set: (v) => store.setPage(v),
})
const pageSize = computed<number>({
  get: () => store.pageSize,
  set: (v) => store.setPageSize(v),
})

const isFiltered = computed(() => {
  const f = store.filters
  return !!(
    f.targetType ||
    f.action ||
    f.actorId ||
    f.targetId ||
    f.dateFrom ||
    f.dateTo ||
    f.keyword
  )
})

const targetTypeOptions: { value: AuditTargetType; label: string }[] = [
  { value: 'PROJECT', label: t('views.finance.auditPage.targetTypes.PROJECT') },
  { value: 'MATERIALS_TASK', label: t('views.finance.auditPage.targetTypes.MATERIALS_TASK') },
  { value: 'DOC_TEMPLATE', label: t('views.finance.auditPage.targetTypes.DOC_TEMPLATE') },
  { value: 'DOC_GENERATION', label: t('views.finance.auditPage.targetTypes.DOC_GENERATION') },
  { value: 'SMTP_CONFIG', label: t('views.finance.auditPage.targetTypes.SMTP_CONFIG') },
  { value: 'OTHER', label: t('views.finance.auditPage.targetTypes.OTHER') },
]

const actionOptions: { value: AuditAction; label: string }[] = [
  { value: 'CREATE', label: t('views.finance.auditPage.actions.CREATE') },
  { value: 'UPDATE', label: t('views.finance.auditPage.actions.UPDATE') },
  { value: 'DELETE', label: t('views.finance.auditPage.actions.DELETE') },
  { value: 'READ', label: t('views.finance.auditPage.actions.READ') },
  { value: 'REVIEW_PASS', label: t('views.finance.auditPage.actions.REVIEW_PASS') },
  { value: 'REVIEW_REJECT', label: t('views.finance.auditPage.actions.REVIEW_REJECT') },
  { value: 'SEND', label: t('views.finance.auditPage.actions.SEND') },
  { value: 'DOWNLOAD', label: t('views.finance.auditPage.actions.DOWNLOAD') },
]

const targetTypeLabel = (value: string): string => {
  const opt = targetTypeOptions.find((o) => o.value === value)
  return opt ? opt.label : value || '-'
}

const actionLabel = (value: string): string => {
  const opt = actionOptions.find((o) => o.value === value)
  return opt ? opt.label : value || '-'
}

const actionTagType = (
  action: string,
): 'info' | 'primary' | 'warning' | 'success' | 'danger' => {
  switch (action) {
    case 'CREATE':
      return 'success'
    case 'UPDATE':
      return 'primary'
    case 'DELETE':
    case 'REVIEW_REJECT':
      return 'danger'
    case 'REVIEW_PASS':
      return 'success'
    case 'SEND':
    case 'DOWNLOAD':
      return 'warning'
    default:
      return 'info'
  }
}

const formatDate = (iso: string): string => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const shortId = (id: string | null | undefined): string => {
  if (!id) return '-'
  // UUIDs are 36 chars with dashes. Show the leading 8 (first group) so
  // operators can correlate without bleeding the full identifier.
  return id.length > 12 ? `${id.slice(0, 8)}…` : id
}

const fetchList = () => {
  if (!isAdmin) return
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  store.fetchList(workspaceId)
}

const debouncedFetch = debounce(fetchList, 300)

function onFilterChange<K extends keyof FinanceAuditFilters>(
  key: K,
  value: FinanceAuditFilters[K],
) {
  store.setFilter(key, value)
  // String filters (keyword, actorId) are debounced so typing doesn't
  // hammer the backend; enum filters fetch immediately for snappy UX.
  if (key === 'keyword' || key === 'actorId' || key === 'targetId') {
    debouncedFetch()
  } else {
    fetchList()
  }
}

const onDateRangeChange = (value: [string, string] | null) => {
  if (value && value.length === 2) {
    store.setFilter('dateFrom', value[0] || '')
    store.setFilter('dateTo', value[1] || '')
  } else {
    store.setFilter('dateFrom', '')
    store.setFilter('dateTo', '')
  }
  filterModel.dateFrom = store.filters.dateFrom
  filterModel.dateTo = store.filters.dateTo
  fetchList()
}

const onReset = () => {
  store.resetFilters()
  Object.assign(filterModel, store.filters)
  dateRange.value = null
  fetchList()
}

const onPageChange = (page: number) => {
  store.setPage(page)
  fetchList()
}

const onSizeChange = (size: number) => {
  store.setPageSize(size)
  fetchList()
}

// ----- CSV export -----
const exporting = ref(false)

/**
 * Build a date-stamped filename and call the export endpoint with the
 * currently-applied filter set. Server is the source of truth for the
 * columns — the frontend just relays the filter params verbatim.
 */
const onExportCsv = async () => {
  if (!isAdmin) return
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  const f = store.filters
  const params = {
    target_type: f.targetType || undefined,
    action: f.action || undefined,
    actor_id: f.actorId || undefined,
    target_id: f.targetId || undefined,
    date_from: f.dateFrom || undefined,
    date_to: f.dateTo || undefined,
    keyword: f.keyword || undefined,
  }
  const today = new Date().toISOString().slice(0, 10)
  exporting.value = true
  try {
    await exportAuditLog(workspaceId, params, `audit-log-${today}.csv`)
  } finally {
    exporting.value = false
  }
}

// ----- payload dialog -----
const payloadDialogVisible = ref(false)
const payloadDialogRow = ref<AuditLogEntry | null>(null)

const openPayloadDialog = (row: AuditLogEntry) => {
  payloadDialogRow.value = row
  payloadDialogVisible.value = true
}

onMounted(() => {
  if (!isAdmin) {
    // Soft-redirect non-admins back to the overview rather than 403.
    router.replace('/finance/overview')
    return
  }
  fetchList()
})
</script>

<style lang="scss" scoped>
.finance-audit {
  &__title {
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 4px;
    color: var(--el-text-color-primary);
  }

  &__subtitle {
    margin: 0;
    color: var(--el-text-color-regular);
    font-size: 13px;
  }

  &__filters {
    background: var(--el-fill-color-light);
    padding: 12px 16px 4px;
    border-radius: 6px;

    :deep(.el-form-item) {
      margin-bottom: 8px;
    }
    // label-position: top 时 label 的小尺寸 + 紧凑间距，避免每个 col 太高
    :deep(.el-form-item__label) {
      padding-bottom: 4px;
      font-size: 13px;
      color: var(--el-text-color-regular);
    }
  }

  &__mono {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
  }

  &__expand {
    padding: 8px 24px 12px;
  }

  &__expand-meta {
    display: flex;
    gap: 24px;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }

  &__expand-label {
    color: var(--el-text-color-secondary);
    margin-right: 6px;
  }

  &__expand-value {
    color: var(--el-text-color-primary);
  }

  &__expand-actions {
    margin-top: 8px;
  }

  /* Payload styling now lives in JsonPayload.vue. We just gap the dialog
     instance from the meta grid above it. */
  &__payload--dialog {
    margin-top: 16px;
  }

  &__dialog-meta {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px 24px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }

  &__pagination {
    margin-top: 16px;
    justify-content: flex-end;
  }

  &__empty {
    text-align: center;
    color: var(--el-text-color-secondary);
    padding: 24px 0;
  }
}

.finance-empty-state {
  text-align: center;
  h3 {
    margin: 8px 0 4px;
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
  p {
    margin: 0 0 12px;
    color: var(--el-text-color-regular);
  }
}
</style>

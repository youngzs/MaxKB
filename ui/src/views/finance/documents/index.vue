<template>
  <div class="finance-documents p-24">
    <div class="finance-documents__header flex-between mb-16">
      <h2 class="finance-documents__title">{{ $t('views.finance.documentsLib.title') }}</h2>
      <el-button v-if="canEdit" type="primary" @click="goWizard">
        <AppIcon iconName="app-add-outlined" class="mr-4" />
        {{ $t('views.finance.documentsLib.newGeneration') }}
      </el-button>
    </div>

    <div class="finance-documents__filters mb-16 flex">
      <el-select
        v-model="projectFilter"
        :placeholder="$t('views.finance.documentsLib.projectFilterAll')"
        clearable
        filterable
        style="width: 240px"
        @change="onProjectChange"
      >
        <el-option
          v-for="p in projectStore.list"
          :key="p.id"
          :label="p.name"
          :value="p.id"
        />
      </el-select>

      <el-select
        v-model="statusFilter"
        :placeholder="$t('views.finance.documentsLib.statusFilterAll')"
        clearable
        style="width: 180px; margin-left: 12px"
        @change="onStatusChange"
      >
        <el-option
          v-for="opt in statusOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
    </div>

    <el-table
      v-loading="store.loading"
      :data="store.list"
      class="finance-documents__table"
      stripe
      style="width: 100%"
      empty-text=" "
    >
      <el-table-column
        :label="$t('views.finance.documentsLib.columns.project')"
        min-width="180"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ projectNameMap[row.project_id] || row.project_id }}
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.documentsLib.columns.template')"
        min-width="180"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ templateNameMap[row.template_id] || row.template_id }}
          <span class="finance-documents__muted">
            v{{ row.template_version_snapshot }}
          </span>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.documentsLib.columns.status')"
        width="140"
      >
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" disable-transitions>
            <AppIcon
              v-if="row.status === 'generating'"
              iconName="app-loading"
              class="mr-4"
              style="vertical-align: middle"
            />
            {{ $t(`views.finance.documentsLib.status.${row.status}`) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.documentsLib.columns.createdAt')"
        min-width="160"
      >
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="created_by"
        :label="$t('views.finance.documentsLib.columns.createdBy')"
        min-width="120"
        show-overflow-tooltip
      />
      <el-table-column
        :label="$t('views.finance.documentsLib.columns.actions')"
        width="280"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            size="small"
            :disabled="!canPreview(row)"
            @click="openPreview(row)"
          >
            {{ $t('views.finance.documentsLib.actions.preview') }}
          </el-button>
          <el-button
            v-if="canEdit && row.status === 'pending_review'"
            link
            type="primary"
            size="small"
            @click="handleConfirm(row)"
          >
            {{ $t('views.finance.documentsLib.actions.confirm') }}
          </el-button>
          <el-button
            v-if="canEdit && row.status === 'confirmed'"
            link
            type="warning"
            size="small"
            @click="handleRevoke(row)"
          >
            {{ $t('views.finance.documentsLib.actions.revoke') }}
          </el-button>
          <el-button
            v-if="row.status === 'generating' || row.status === 'failed'"
            link
            type="primary"
            size="small"
            @click="openRunLog(row)"
          >
            {{ $t('views.finance.workflowRun.openLogLink') }}
          </el-button>
          <el-button
            link
            type="primary"
            size="small"
            :disabled="!canDownload(row)"
            @click="handleDownload(row)"
          >
            {{ $t('views.finance.documentsLib.actions.download') }}
          </el-button>
        </template>
      </el-table-column>

      <template #empty>
        <el-empty
          v-if="!isFiltered"
          :image-size="100"
          class="finance-documents__empty"
        >
          <template #description>
            <div class="finance-empty-state">
              <h3>{{ $t('views.finance.documentsLib.emptyState.title') }}</h3>
              <p class="text-secondary">{{ $t('views.finance.documentsLib.emptyState.subtitle') }}</p>
              <el-button v-if="canEdit" type="primary" @click="goWizard">
                {{ $t('views.finance.documentsLib.emptyState.cta') }}
              </el-button>
            </div>
          </template>
        </el-empty>
        <div v-else class="finance-documents__empty">
          <p>{{ $t('views.finance.documentsLib.emptyFiltered') }}</p>
        </div>
      </template>
    </el-table>

    <div v-if="store.total > 0" class="finance-documents__pagination flex">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="store.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>

    <el-drawer
      v-model="previewDrawerVisible"
      :title="$t('views.finance.documentsLib.previewTitle')"
      size="60%"
      direction="rtl"
      destroy-on-close
    >
      <DocxPreview
        v-if="previewTarget"
        :workspace-id="previewWorkspaceId"
        :generation-id="previewTarget.id"
      />
    </el-drawer>

    <!-- Workflow run drawer (Gate 7 Track B) -->
    <WorkflowRunDrawer
      v-if="runLogTarget"
      v-model:visible="runLogDrawerVisible"
      :workspace-id="runLogWorkspaceId"
      target-type="DOC_GENERATION"
      :target-id="runLogTarget.id"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { MsgConfirm, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import type { Generation, GenerationStatus } from '@/api/finance/type'
import DocxPreview from '@/components/docx-preview/index.vue'
import WorkflowRunDrawer from '../components/WorkflowRunDrawer.vue'

const router = useRouter()
const {
  user,
  financeGeneration: store,
  financeProject: projectStore,
  financeTemplate: templateStore,
} = useStore()

const projectFilter = ref<string>(store.projectFilter)
const statusFilter = ref<'' | GenerationStatus>(store.statusFilter)

const previewDrawerVisible = ref(false)
const previewTarget = ref<Generation | null>(null)

// Gate 7 Track B: workflow-run drawer for in-flight / failed generations.
const runLogDrawerVisible = ref(false)
const runLogTarget = ref<Generation | null>(null)
const runLogWorkspaceId = computed<string>(() =>
  String(user.getWorkspaceId() || ''),
)
const openRunLog = (row: Generation) => {
  runLogTarget.value = row
  runLogDrawerVisible.value = true
}

const canEdit = computed(() =>
  hasPermission(
    [
      RoleConst.ADMIN,
      RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
      PermissionConst.FINANCE_EDIT.getWorkspacePermission,
      PermissionConst.FINANCE_EDIT.getWorkspacePermissionWorkspaceManageRole,
    ],
    'OR',
  ),
)

const previewWorkspaceId = computed(() => user.getWorkspaceId() || '')

const currentPage = computed<number>({
  get: () => store.currentPage,
  set: (v) => store.setPage(v),
})
const pageSize = computed<number>({
  get: () => store.pageSize,
  set: (v) => store.setPageSize(v),
})

const isFiltered = computed(() => !!store.projectFilter || !!store.statusFilter)

const statusOptions: { value: GenerationStatus; label: string }[] = [
  { value: 'generating', label: t('views.finance.documentsLib.status.generating') },
  { value: 'pending_review', label: t('views.finance.documentsLib.status.pending_review') },
  { value: 'confirmed', label: t('views.finance.documentsLib.status.confirmed') },
  { value: 'revoked', label: t('views.finance.documentsLib.status.revoked') },
  { value: 'failed', label: t('views.finance.documentsLib.status.failed') },
]

const statusTagType = (
  status: GenerationStatus,
): 'info' | 'primary' | 'warning' | 'success' | 'danger' => {
  switch (status) {
    case 'generating':
      return 'info'
    case 'pending_review':
      return 'warning'
    case 'confirmed':
      return 'success'
    case 'revoked':
      return 'info'
    case 'failed':
      return 'danger'
    default:
      return 'info'
  }
}

const projectNameMap = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const p of projectStore.list) map[p.id] = p.name
  return map
})

const templateNameMap = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const tpl of templateStore.list) map[tpl.id] = tpl.name
  return map
})

const formatDate = (iso: string): string => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const canPreview = (row: Generation) =>
  row.status === 'pending_review' ||
  row.status === 'confirmed' ||
  row.status === 'revoked'

const canDownload = (row: Generation) =>
  (row.status === 'pending_review' ||
    row.status === 'confirmed' ||
    row.status === 'revoked') &&
  !!row.output_oss_key

const fetchList = () => {
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  store.fetchList(workspaceId)
}

// Gate 7 Track B: generation is now async (status stays `generating` until
// the Celery worker finishes). Poll lightly while any visible row is still
// in flight so the table catches up without a manual refresh.
let generatingPoll: ReturnType<typeof setInterval> | null = null
const stopGeneratingPoll = () => {
  if (generatingPoll) {
    clearInterval(generatingPoll)
    generatingPoll = null
  }
}
const startGeneratingPoll = () => {
  stopGeneratingPoll()
  generatingPoll = setInterval(() => {
    const hasInFlight = (store.list || []).some(
      (g: Generation) => g.status === 'generating',
    )
    if (!hasInFlight) {
      stopGeneratingPoll()
      return
    }
    fetchList()
  }, 4000)
}

const onProjectChange = (val: string | undefined) => {
  const id = val || ''
  store.setProjectFilter(id)
  fetchList()
}

const onStatusChange = (val: string | undefined) => {
  const s = (val || '') as '' | GenerationStatus
  store.setStatusFilter(s)
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

const goWizard = () => {
  router.push({ name: 'finance-documents-wizard' })
}

const openPreview = (row: Generation) => {
  previewTarget.value = row
  previewDrawerVisible.value = true
}

const handleConfirm = async (row: Generation) => {
  try {
    await MsgConfirm(
      t('views.finance.documentsLib.confirmTitle'),
      t('views.finance.documentsLib.confirmDesc'),
    )
  } catch {
    return
  }
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  await store.confirm(workspaceId, row.id)
  MsgSuccess(t('views.finance.documentsLib.confirmSuccess'))
}

const handleRevoke = async (row: Generation) => {
  try {
    await MsgConfirm(
      t('views.finance.documentsLib.revokeTitle'),
      t('views.finance.documentsLib.revokeDesc'),
      { confirmButtonClass: 'danger' },
    )
  } catch {
    return
  }
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  await store.revoke(workspaceId, row.id)
  MsgSuccess(t('views.finance.documentsLib.revokeSuccess'))
}

const handleDownload = async (row: Generation) => {
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  const fallback = t('views.finance.documentsLib.downloadFallbackName')
  await store.download(workspaceId, row.id, fallback)
}

onMounted(async () => {
  projectFilter.value = store.projectFilter
  statusFilter.value = store.statusFilter
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  // Fetch projects and templates so we can resolve names in the table.
  // Bound list size with a one-off larger page; deep pagination is handled
  // on each module's own page.
  projectStore.pageSize = 100
  templateStore.pageSize = 100
  await Promise.all([
    projectStore.fetchList(workspaceId),
    templateStore.fetchList(workspaceId),
  ])
  fetchList()
})
</script>

<style lang="scss" scoped>
.finance-documents {
  min-height: calc(100vh - 80px);
  background: var(--el-bg-color);

  &__header {
    align-items: center;
  }

  &__title {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__filters {
    align-items: center;
  }

  &__muted {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    margin-left: 4px;
  }

  &__empty {
    padding: 32px 0;
    text-align: center;
    color: var(--el-text-color-regular);
    p {
      margin: 0 0 12px;
    }
  }

  &__pagination {
    justify-content: flex-end;
    margin-top: 16px;
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

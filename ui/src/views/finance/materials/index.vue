<template>
  <div class="finance-materials p-24">
    <div class="finance-materials__header flex-between mb-16">
      <h2 class="finance-materials__title">
        {{ $t('views.finance.materials.title') }}
      </h2>
      <el-button v-if="canEdit" type="primary" @click="openCreate">
        <AppIcon iconName="app-add-outlined" class="mr-4" />
        {{ $t('views.finance.materials.newTask') }}
      </el-button>
    </div>

    <div class="finance-materials__filters mb-16 flex">
      <el-select
        v-model="projectFilter"
        :placeholder="$t('views.finance.materials.list.projectFilterAll')"
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
        :placeholder="$t('views.finance.materials.list.statusFilterAll')"
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
      class="finance-materials__table"
      stripe
      style="width: 100%"
      empty-text=" "
    >
      <el-table-column
        prop="title"
        :label="$t('views.finance.materials.list.columns.title')"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <a class="finance-materials__link" @click="goDetail(row)">
            {{ row.title }}
          </a>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.materials.list.columns.project')"
        min-width="160"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ projectNameMap[row.project_id] || row.project_id }}
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.materials.list.columns.status')"
        width="140"
      >
        <template #default="{ row }">
          <el-tag
            :type="statusTagType(row.status)"
            disable-transitions
            effect="plain"
          >
            <AppIcon
              v-if="row.status === 'parsing' || row.status === 'matching'"
              iconName="app-loading"
              class="mr-4"
              style="vertical-align: middle"
            />
            {{ $t(`views.finance.materials.status.${row.status}`) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.materials.list.columns.items')"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          {{ row.parsed_items?.length || 0 }}
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.materials.list.columns.selected')"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          {{ row.selected_documents?.length || 0 }}
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.materials.list.columns.createdAt')"
        min-width="160"
      >
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.materials.list.columns.actions')"
        width="220"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'draft'"
            link
            type="primary"
            size="small"
            @click="goDetail(row)"
          >
            {{ $t('views.finance.materials.list.actions.resume') }}
          </el-button>
          <el-button
            v-else
            link
            type="primary"
            size="small"
            @click="goDetail(row)"
          >
            {{ $t('views.finance.materials.list.actions.view') }}
          </el-button>
          <el-button
            v-if="canEdit"
            link
            type="danger"
            size="small"
            @click="handleDelete(row)"
          >
            {{ $t('views.finance.materials.list.actions.delete') }}
          </el-button>
        </template>
      </el-table-column>

      <template #empty>
        <el-empty
          v-if="!isFiltered"
          :image-size="100"
          class="finance-materials__empty"
        >
          <template #description>
            <div class="finance-empty-state">
              <h3>{{ $t('views.finance.materials.emptyState.title') }}</h3>
              <p class="text-secondary">{{ $t('views.finance.materials.emptyState.subtitle') }}</p>
              <el-button v-if="canEdit" type="primary" @click="openCreate">
                {{ $t('views.finance.materials.emptyState.cta') }}
              </el-button>
            </div>
          </template>
        </el-empty>
        <div v-else class="finance-materials__empty">
          <p>{{ $t('views.finance.materials.emptyFiltered') }}</p>
        </div>
      </template>
    </el-table>

    <div class="finance-materials__pagination flex" v-if="store.total > 0">
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

    <CreateTaskDialog v-model="dialogVisible" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { MsgConfirm, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import type { MaterialsTask, MaterialsTaskStatus } from '@/api/finance/type'
import CreateTaskDialog from './components/CreateTaskDialog.vue'

const router = useRouter()
const {
  user,
  financeProject: projectStore,
  financeMaterials: store,
} = useStore()

const dialogVisible = ref(false)
const projectFilter = ref<string>(store.projectFilter)
const statusFilter = ref<'' | MaterialsTaskStatus>(store.statusFilter)
let pollTimer: ReturnType<typeof setInterval> | null = null

const currentPage = computed<number>({
  get: () => store.currentPage,
  set: (v) => store.setPage(v),
})
const pageSize = computed<number>({
  get: () => store.pageSize,
  set: (v) => store.setPageSize(v),
})

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

const isFiltered = computed(
  () => !!store.projectFilter || !!store.statusFilter,
)

const statusOptions: { value: MaterialsTaskStatus; label: string }[] = [
  { value: 'draft', label: t('views.finance.materials.status.draft') },
  { value: 'parsing', label: t('views.finance.materials.status.parsing') },
  { value: 'matching', label: t('views.finance.materials.status.matching') },
  {
    value: 'pending_review',
    label: t('views.finance.materials.status.pending_review'),
  },
  { value: 'approved', label: t('views.finance.materials.status.approved') },
  { value: 'sent', label: t('views.finance.materials.status.sent') },
  { value: 'rejected', label: t('views.finance.materials.status.rejected') },
  { value: 'failed', label: t('views.finance.materials.status.failed') },
]

const projectNameMap = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const p of projectStore.list) {
    map[p.id] = p.name
  }
  return map
})

const statusTagType = (
  status: MaterialsTaskStatus,
): 'info' | 'primary' | 'warning' | 'success' | 'danger' => {
  switch (status) {
    case 'draft':
      return 'info'
    case 'parsing':
    case 'matching':
      return 'warning'
    case 'pending_review':
      return 'primary'
    case 'approved':
    case 'sent':
      return 'success'
    case 'rejected':
    case 'failed':
      return 'danger'
    default:
      return 'info'
  }
}

const formatDate = (iso: string): string => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const fetchList = () => {
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  store.fetchList(workspaceId)
}

const onProjectChange = (val: string | null) => {
  store.setProjectFilter(val || '')
  fetchList()
}

const onStatusChange = (val: '' | MaterialsTaskStatus | null) => {
  store.setStatusFilter(val || '')
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

const openCreate = () => {
  dialogVisible.value = true
}

const goDetail = (row: MaterialsTask) => {
  router.push({
    name: 'finance-materials-detail',
    params: { pk: row.id },
  })
}

const handleDelete = async (row: MaterialsTask) => {
  try {
    await MsgConfirm(
      t('common.tip'),
      t('views.finance.materials.deleteConfirm', { title: row.title }),
      { confirmButtonClass: 'danger' },
    )
  } catch {
    return
  }
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  await store.remove(workspaceId, row.id)
  MsgSuccess(t('views.finance.materials.deleteSuccess'))
}

const startPollingIfNeeded = () => {
  // If any visible row is in a transient state, poll every 3 s.
  if (!store.hasTransientInList) {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    return
  }
  if (pollTimer) return
  pollTimer = setInterval(() => {
    const workspaceId = user.getWorkspaceId()
    if (!workspaceId) return
    store
      .refreshListSilent(workspaceId)
      .catch(() => undefined)
      .finally(() => {
        // Re-evaluate after each refresh — may need to stop.
        if (!store.hasTransientInList && pollTimer) {
          clearInterval(pollTimer)
          pollTimer = null
        }
      })
  }, 3000)
}

watch(
  () => store.list,
  () => startPollingIfNeeded(),
  { deep: false },
)

onMounted(() => {
  projectFilter.value = store.projectFilter
  statusFilter.value = store.statusFilter
  const wid = user.getWorkspaceId()
  if (wid && projectStore.list.length === 0) {
    projectStore.fetchList(wid).catch(() => undefined)
  }
  fetchList()
})

onBeforeUnmount(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style lang="scss" scoped>
.finance-materials {
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

  &__link {
    color: var(--el-color-primary);
    cursor: pointer;
    &:hover {
      text-decoration: underline;
    }
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

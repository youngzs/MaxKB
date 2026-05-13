<template>
  <div class="finance-project p-24">
    <div class="finance-project__header flex-between mb-16">
      <h2 class="finance-project__title">{{ $t('views.finance.project.title') }}</h2>
      <el-button
        v-if="canEdit"
        type="primary"
        @click="openCreate"
      >
        <AppIcon iconName="app-add-outlined" class="mr-4" />
        {{ $t('views.finance.project.newProject') }}
      </el-button>
    </div>

    <div class="finance-project__filters mb-16 flex">
      <el-input
        v-model="keywordInput"
        :placeholder="$t('views.finance.project.searchPlaceholder')"
        clearable
        style="width: 260px"
        @input="onKeywordInput"
        @clear="onKeywordInput('')"
      />

      <el-select
        v-model="statusFilterInput"
        :placeholder="$t('views.finance.project.statusFilterAll')"
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
      class="finance-project__table"
      stripe
      style="width: 100%"
      empty-text=" "
    >
      <el-table-column
        prop="name"
        :label="$t('views.finance.project.columns.name')"
        min-width="180"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <a class="finance-project__link" @click="goDetail(row)">{{ row.name }}</a>
        </template>
      </el-table-column>
      <el-table-column
        prop="code"
        :label="$t('views.finance.project.columns.code')"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span>{{ row.code || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.project.columns.type')"
        min-width="120"
      >
        <template #default="{ row }">
          {{ $t(`views.finance.project.projectType.${row.project_type}`) }}
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.project.columns.status')"
        min-width="110"
      >
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" disable-transitions>
            {{ $t(`views.finance.project.statusOptions.${row.status}`) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.project.columns.targetAmount')"
        min-width="160"
      >
        <template #default="{ row }">
          <span>{{ formatAmount(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="region"
        :label="$t('views.finance.project.columns.region')"
        min-width="100"
      >
        <template #default="{ row }">
          <span>{{ row.region || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.project.columns.createdAt')"
        min-width="160"
      >
        <template #default="{ row }">
          <span>{{ formatDate(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.project.columns.actions')"
        width="200"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="goDetail(row)">
            {{ $t('views.finance.project.actions.view') }}
          </el-button>
          <el-button
            v-if="canEdit"
            link
            type="primary"
            size="small"
            @click="openEdit(row)"
          >
            {{ $t('views.finance.project.actions.edit') }}
          </el-button>
          <el-button
            v-if="canEdit"
            link
            type="danger"
            size="small"
            @click="handleDelete(row)"
          >
            {{ $t('views.finance.project.actions.delete') }}
          </el-button>
        </template>
      </el-table-column>

      <template #empty>
        <div class="finance-project__empty">
          <p>
            {{
              isFiltered
                ? $t('views.finance.project.emptyFiltered')
                : $t('views.finance.project.empty')
            }}
          </p>
          <el-button
            v-if="canEdit && !isFiltered"
            type="primary"
            @click="openCreate"
          >
            {{ $t('views.finance.project.newProject') }}
          </el-button>
        </div>
      </template>
    </el-table>

    <div class="finance-project__pagination flex" v-if="store.total > 0">
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

    <ProjectFormDialog
      v-model="dialogVisible"
      :initial="editing"
      @success="onSaveSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { debounce } from 'lodash'
import { MsgConfirm, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst } from '@/utils/permission/data'
import type { Project, ProjectStatus } from '@/api/finance/type'
import ProjectFormDialog from './components/ProjectFormDialog.vue'

const router = useRouter()
const { user, financeProject: store } = useStore()

const dialogVisible = ref(false)
const editing = ref<Project | null>(null)
const keywordInput = ref(store.keyword)
const statusFilterInput = ref<'' | ProjectStatus>(store.statusFilter)

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
      PermissionConst.FINANCE_EDIT.getWorkspacePermission,
      PermissionConst.FINANCE_EDIT.getWorkspacePermissionWorkspaceManageRole,
    ],
    'OR',
  ),
)

const isFiltered = computed(() => !!store.keyword || !!store.statusFilter)

const statusOptions: { value: ProjectStatus; label: string }[] = [
  { value: 'preparing', label: t('views.finance.project.statusOptions.preparing') },
  { value: 'materials', label: t('views.finance.project.statusOptions.materials') },
  { value: 'engaging', label: t('views.finance.project.statusOptions.engaging') },
  { value: 'landed', label: t('views.finance.project.statusOptions.landed') },
  { value: 'terminated', label: t('views.finance.project.statusOptions.terminated') },
]

const statusTagType = (
  status: ProjectStatus,
): 'info' | 'primary' | 'warning' | 'success' | 'danger' => {
  switch (status) {
    case 'preparing':
      return 'info'
    case 'materials':
      return 'primary'
    case 'engaging':
      return 'warning'
    case 'landed':
      return 'success'
    case 'terminated':
      return 'danger'
    default:
      return 'info'
  }
}

const formatAmount = (row: Project): string => {
  if (row.target_amount === null || row.target_amount === undefined || row.target_amount === '') {
    return '-'
  }
  const num = Number(row.target_amount)
  if (!Number.isFinite(num)) return row.target_amount
  return `${num.toLocaleString()} ${row.currency || 'CNY'}`
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

const debouncedFetch = debounce(fetchList, 300)

const onKeywordInput = (val: string) => {
  store.setKeyword(val)
  debouncedFetch()
}

const onStatusChange = (val: '' | ProjectStatus) => {
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
  editing.value = null
  dialogVisible.value = true
}

const openEdit = (row: Project) => {
  editing.value = row
  dialogVisible.value = true
}

const goDetail = (row: Project) => {
  router.push({ name: 'finance-project-detail', params: { pk: row.id } })
}

const handleDelete = async (row: Project) => {
  try {
    await MsgConfirm(
      t('common.tip'),
      t('views.finance.project.deleteConfirm', { name: row.name }),
      { confirmButtonClass: 'danger' },
    )
  } catch {
    return
  }
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  await store.remove(workspaceId, row.id)
  MsgSuccess(t('views.finance.project.deleteSuccess'))
}

const onSaveSuccess = () => {
  fetchList()
}

onMounted(() => {
  keywordInput.value = store.keyword
  statusFilterInput.value = store.statusFilter
  fetchList()
})
</script>

<style lang="scss" scoped>
.finance-project {
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
</style>

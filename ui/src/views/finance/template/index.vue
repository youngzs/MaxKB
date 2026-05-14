<template>
  <div class="finance-template p-24">
    <div class="finance-template__header flex-between mb-16">
      <h2 class="finance-template__title">{{ $t('views.finance.templateLib.title') }}</h2>
      <el-button v-if="canEdit" type="primary" @click="openUpload">
        <AppIcon iconName="app-add-outlined" class="mr-4" />
        {{ $t('views.finance.templateLib.upload') }}
      </el-button>
    </div>

    <div class="finance-template__filters mb-16">
      <el-radio-group v-model="scenarioFilter" @change="onScenarioChange">
        <el-radio-button label="">
          {{ $t('views.finance.templateLib.scenario.all') }}
        </el-radio-button>
        <el-radio-button
          v-for="opt in scenarioOptions"
          :key="opt.value"
          :label="opt.value"
        >
          {{ opt.label }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <div v-loading="store.loading" class="finance-template__body">
      <div v-if="store.list.length > 0" class="finance-template__grid">
        <el-card
          v-for="tpl in store.list"
          :key="tpl.id"
          class="finance-template__card"
          shadow="hover"
        >
          <div class="finance-template__card-header">
            <el-tag size="small" :type="scenarioTagType(tpl.scenario)" disable-transitions>
              {{ $t(`views.finance.templateLib.scenario.${tpl.scenario}`) }}
            </el-tag>
            <el-tag
              v-if="!tpl.is_active"
              size="small"
              type="info"
              class="ml-4"
              disable-transitions
            >
              {{ $t('views.finance.templateLib.fields.isActive') }}
            </el-tag>
          </div>
          <h3 class="finance-template__card-name" @click="goDetail(tpl)">
            {{ tpl.name }}
          </h3>
          <div class="finance-template__card-meta">
            <span>
              {{ $t('views.finance.templateLib.fields.placeholderCount') }}:
              {{ tpl.placeholders?.length || 0 }}
            </span>
            <span>
              {{ $t('views.finance.templateLib.fields.version') }}:
              v{{ tpl.version }}
            </span>
          </div>
          <div class="finance-template__card-meta">
            <span>
              {{ $t('views.finance.templateLib.fields.updatedAt') }}:
              {{ formatDate(tpl.updated_at) }}
            </span>
          </div>
          <div class="finance-template__card-actions">
            <el-button link type="primary" size="small" @click="goDetail(tpl)">
              {{ $t('views.finance.templateLib.actions.view') }}
            </el-button>
            <el-button
              v-if="canEdit"
              link
              type="primary"
              size="small"
              @click="goDetail(tpl)"
            >
              {{ $t('views.finance.templateLib.actions.edit') }}
            </el-button>
            <el-button
              v-if="canEdit"
              link
              type="danger"
              size="small"
              @click="handleDelete(tpl)"
            >
              {{ $t('views.finance.templateLib.actions.delete') }}
            </el-button>
          </div>
        </el-card>
      </div>

      <div v-else-if="!store.loading" class="finance-template__empty">
        <p>
          {{
            scenarioFilter
              ? $t('views.finance.templateLib.emptyFiltered')
              : $t('views.finance.templateLib.empty')
          }}
        </p>
        <el-button v-if="canEdit && !scenarioFilter" type="primary" @click="openUpload">
          {{ $t('views.finance.templateLib.upload') }}
        </el-button>
      </div>
    </div>

    <div v-if="store.total > 0" class="finance-template__pagination flex">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="store.total"
        :page-sizes="[12, 24, 48]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>

    <UploadTemplateDialog v-model="uploadDialogVisible" @success="onUploadSuccess" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { MsgConfirm, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import type { Template, TemplateScenario } from '@/api/finance/type'
import UploadTemplateDialog from './components/UploadTemplateDialog.vue'

const router = useRouter()
const { user, financeTemplate: store } = useStore()

const uploadDialogVisible = ref(false)
const scenarioFilter = ref<'' | TemplateScenario>(store.scenarioFilter)

const canEdit = computed(() =>
  hasPermission(
    [
      RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
      PermissionConst.FINANCE_EDIT.getWorkspacePermission,
      PermissionConst.FINANCE_EDIT.getWorkspacePermissionWorkspaceManageRole,
    ],
    'OR',
  ),
)

const currentPage = computed<number>({
  get: () => store.currentPage,
  set: (v) => store.setPage(v),
})
const pageSize = computed<number>({
  get: () => store.pageSize,
  set: (v) => store.setPageSize(v),
})

const scenarioOptions: { value: TemplateScenario; label: string }[] = [
  { value: 'internal_report', label: t('views.finance.templateLib.scenario.internal_report') },
  { value: 'meeting', label: t('views.finance.templateLib.scenario.meeting') },
  { value: 'system_process', label: t('views.finance.templateLib.scenario.system_process') },
  { value: 'other', label: t('views.finance.templateLib.scenario.other') },
]

const scenarioTagType = (
  scenario: TemplateScenario,
): 'info' | 'primary' | 'warning' | 'success' | 'danger' => {
  switch (scenario) {
    case 'internal_report':
      return 'primary'
    case 'meeting':
      return 'warning'
    case 'system_process':
      return 'success'
    case 'other':
      return 'info'
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

const onScenarioChange = (val: string | number | boolean | undefined) => {
  const filter = (val ?? '') as '' | TemplateScenario
  scenarioFilter.value = filter
  store.setScenarioFilter(filter)
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

const openUpload = () => {
  uploadDialogVisible.value = true
}

const goDetail = (tpl: Template) => {
  router.push({ name: 'finance-template-detail', params: { pk: tpl.id } })
}

const handleDelete = async (tpl: Template) => {
  try {
    await MsgConfirm(
      t('common.tip'),
      t('views.finance.templateLib.deleteConfirm', { name: tpl.name }),
      { confirmButtonClass: 'danger' },
    )
  } catch {
    return
  }
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  await store.remove(workspaceId, tpl.id)
  MsgSuccess(t('views.finance.templateLib.deleteSuccess'))
}

const onUploadSuccess = (tpl: Template) => {
  // Jump to detail page so the user can curate placeholder metadata next.
  router.push({ name: 'finance-template-detail', params: { pk: tpl.id } })
}

onMounted(() => {
  scenarioFilter.value = store.scenarioFilter
  fetchList()
})
</script>

<style lang="scss" scoped>
.finance-template {
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
    display: flex;
    align-items: center;
  }

  &__body {
    min-height: 240px;
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  &__card {
    cursor: default;
    transition: transform 0.15s ease;
    &:hover {
      transform: translateY(-2px);
    }
  }

  &__card-header {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }

  &__card-name {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 12px;
    color: var(--el-color-primary);
    cursor: pointer;
    &:hover {
      text-decoration: underline;
    }
  }

  &__card-meta {
    color: var(--el-text-color-regular);
    font-size: 13px;
    margin-bottom: 4px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }

  &__card-actions {
    margin-top: 12px;
    display: flex;
    justify-content: flex-end;
    gap: 4px;
  }

  &__empty {
    padding: 64px 0;
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

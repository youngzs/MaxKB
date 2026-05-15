<template>
  <div class="finance-project-detail p-24" v-loading="loading">
    <div class="finance-project-detail__header flex-between mb-24">
      <div class="flex" style="align-items: center; gap: 12px">
        <el-button link @click="goBack">
          {{ $t('views.finance.project.backToList') }}
        </el-button>
        <h2 class="finance-project-detail__title" v-if="project">
          {{ project.name }}
        </h2>
        <el-tag v-if="project" :type="statusTagType(project.status)" disable-transitions>
          {{ $t(`views.finance.project.statusOptions.${project.status}`) }}
        </el-tag>
      </div>
      <el-button
        v-if="project && canEdit"
        type="primary"
        @click="dialogVisible = true"
      >
        {{ $t('views.finance.project.actions.edit') }}
      </el-button>
    </div>

    <el-card v-if="project" shadow="never" class="mb-16">
      <template #header>
        <strong>{{ $t('views.finance.project.sections.basic') }}</strong>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="$t('views.finance.project.fields.code')">
          {{ project.code || $t('views.finance.project.notSet') }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('views.finance.project.fields.projectType')">
          {{ $t(`views.finance.project.projectType.${project.project_type}`) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('views.finance.project.fields.targetAmount')">
          {{ formatAmount(project) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('views.finance.project.fields.currency')">
          {{ project.currency || $t('views.finance.project.notSet') }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('views.finance.project.fields.region')">
          {{ project.region || $t('views.finance.project.notSet') }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('views.finance.project.fields.industryCode')">
          {{ project.industry_code || $t('views.finance.project.notSet') }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('views.finance.project.fields.description')" :span="2">
          {{ project.description || $t('views.finance.project.notSet') }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="project" shadow="never" class="mb-16">
      <template #header>
        <strong>{{ $t('views.finance.project.sections.knowledge') }}</strong>
      </template>
      <div v-if="project.knowledge_base_ids && project.knowledge_base_ids.length">
        <el-tag
          v-for="id in project.knowledge_base_ids"
          :key="id"
          class="mr-8"
          disable-transitions
        >
          {{ id }}
        </el-tag>
      </div>
      <div v-else class="finance-project-detail__placeholder">
        {{ $t('views.finance.project.knowledgeBasePending') }}
      </div>
    </el-card>

    <el-card v-if="project" shadow="never">
      <template #header>
        <strong>{{ $t('views.finance.project.sections.auditLog') }}</strong>
      </template>
      <div class="finance-project-detail__placeholder">
        {{ $t('views.finance.project.sections.auditLogPlaceholder') }}
      </div>
    </el-card>

    <ProjectFormDialog
      v-model="dialogVisible"
      :initial="project"
      @success="onSaveSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import type { Project, ProjectStatus } from '@/api/finance/type'
import ProjectFormDialog from './components/ProjectFormDialog.vue'

const route = useRoute()
const router = useRouter()
const { user, financeProject: store } = useStore()

const loading = ref(false)
const dialogVisible = ref(false)
const project = ref<Project | null>(null)

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

const formatAmount = (p: Project): string => {
  if (p.target_amount === null || p.target_amount === undefined || p.target_amount === '') {
    return '-'
  }
  const num = Number(p.target_amount)
  if (!Number.isFinite(num)) return p.target_amount
  return `${num.toLocaleString()} ${p.currency || 'CNY'}`
}

const fetchDetail = async () => {
  const workspaceId = user.getWorkspaceId()
  const pk = route.params.pk as string
  if (!workspaceId || !pk) return
  loading.value = true
  try {
    const data = await store.fetchDetail(workspaceId, pk)
    project.value = data
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push({ name: 'finance-project' })
}

const onSaveSuccess = (updated: Project) => {
  project.value = updated
}

// `immediate: true` covers the case where Vue Router re-uses the parent
// route component on first SPA navigation from the list — in that scenario
// onMounted fires before route.params.pk is fully populated, so the plain
// onMounted-only path was leaving the page blank until a hard refresh.
// Running the watcher immediately closes the race; the route.name guard
// keeps it from firing when navigating away.
watch(
  () => route.params.pk,
  () => {
    if (route.name === 'finance-project-detail') fetchDetail()
  },
  { immediate: true },
)
</script>

<style lang="scss" scoped>
.finance-project-detail {
  min-height: calc(100vh - 80px);
  background: var(--el-bg-color);

  &__title {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }

  &__placeholder {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
}
</style>

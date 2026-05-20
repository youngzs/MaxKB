<template>
  <div class="finance-progress p-24">
    <div class="finance-progress__header flex-between mb-16">
      <h2 class="finance-progress__title">{{ $t('views.finance.progress') }}</h2>
      <el-button @click="refresh">
        {{ $t('views.finance.progressPage.refresh') }}
      </el-button>
    </div>

    <div class="finance-progress__kpis mb-16">
      <div v-for="k in kpis" :key="k.key" class="finance-progress__kpi">
        <div class="finance-progress__kpi-label">{{ k.label }}</div>
        <div class="finance-progress__kpi-value" :class="'is-' + k.tone">
          {{ k.value }}
        </div>
        <div v-if="k.hint" class="finance-progress__kpi-hint">{{ k.hint }}</div>
      </div>
    </div>

    <div class="finance-progress__filters mb-12 flex">
      <el-select
        v-model="typeFilter"
        clearable
        :placeholder="$t('views.finance.progressPage.allTypes')"
        style="width: 150px"
        @change="fetchGantt"
      >
        <el-option
          v-for="o in typeOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <el-select
        v-model="statusFilter"
        clearable
        :placeholder="$t('views.finance.progressPage.allStatuses')"
        style="width: 150px; margin-left: 12px"
        @change="fetchGantt"
      >
        <el-option
          v-for="o in statusOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <el-select
        v-model="ownerFilter"
        clearable
        filterable
        :placeholder="$t('views.finance.progressPage.allOwners')"
        style="width: 180px; margin-left: 12px"
        @change="fetchGantt"
      >
        <el-option
          v-for="o in ownerOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>

      <div class="finance-progress__legend">
        <span
          v-for="lg in legend"
          :key="lg.key"
          class="finance-progress__legend-item"
        >
          <i class="finance-progress__dot" :class="'is-' + lg.key" />
          {{ lg.label }}
        </span>
      </div>
    </div>

    <div v-loading="loading" class="finance-progress__body">
      <ProgressGantt
        v-if="projects.length"
        :projects="projects"
        :owner-name-map="ownerNameMap"
        @select="onSelect"
      />
      <el-empty
        v-else-if="!loading"
        :description="$t('views.finance.progressPage.empty')"
        :image-size="100"
      />
    </div>

    <ProjectStageDrawer
      v-model:visible="drawerVisible"
      :workspace-id="workspaceId"
      :project="selectedProject"
      :can-edit="canEdit"
      :owner-name-map="ownerNameMap"
      :owner-options="ownerOptions"
      @changed="refresh"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import useStore from '@/stores'
import { t } from '@/locales'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import type {
  DashboardData,
  GanttProject,
  ProjectStatus,
  ProjectType,
} from '@/api/finance/type'
import { getDashboard, getGanttData } from '@/api/finance/progress'
import UserApi from '@/api/user/user'
import ProgressGantt from './components/ProgressGantt.vue'
import ProjectStageDrawer from './components/ProjectStageDrawer.vue'

interface OwnerOption {
  label: string
  value: string
}

const { user } = useStore()
const workspaceId = computed(() => user.getWorkspaceId() || '')

const loading = ref(false)
const projects = ref<GanttProject[]>([])
const dashboard = ref<DashboardData | null>(null)
const typeFilter = ref<ProjectType | ''>('')
const statusFilter = ref<ProjectStatus | ''>('')
const ownerFilter = ref('')

const ownerOptions = ref<OwnerOption[]>([])
const ownerNameMap = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  ownerOptions.value.forEach((o) => {
    map[o.value] = o.label
  })
  return map
})

const drawerVisible = ref(false)
const selectedProject = ref<GanttProject | null>(null)

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

const typeOptions: { value: ProjectType; label: string }[] = [
  { value: 'bank_loan', label: t('views.finance.project.projectType.bank_loan') },
  { value: 'bond', label: t('views.finance.project.projectType.bond') },
  { value: 'trust', label: t('views.finance.project.projectType.trust') },
  { value: 'abs', label: t('views.finance.project.projectType.abs') },
  { value: 'other', label: t('views.finance.project.projectType.other') },
]

const statusOptions: { value: ProjectStatus; label: string }[] = [
  { value: 'preparing', label: t('views.finance.project.statusOptions.preparing') },
  { value: 'materials', label: t('views.finance.project.statusOptions.materials') },
  { value: 'engaging', label: t('views.finance.project.statusOptions.engaging') },
  { value: 'landed', label: t('views.finance.project.statusOptions.landed') },
  { value: 'terminated', label: t('views.finance.project.statusOptions.terminated') },
]

const legend = computed(() => [
  { key: 'done', label: t('views.finance.progressPage.stageStatus.done') },
  { key: 'active', label: t('views.finance.progressPage.stageStatus.active') },
  { key: 'pending', label: t('views.finance.progressPage.stageStatus.pending') },
  { key: 'skipped', label: t('views.finance.progressPage.stageStatus.skipped') },
])

async function fetchGantt() {
  if (!workspaceId.value) return
  loading.value = true
  try {
    const res = await getGanttData(workspaceId.value, {
      project_type: typeFilter.value || undefined,
      status: statusFilter.value || undefined,
      owner_id: ownerFilter.value || undefined,
    })
    projects.value = res?.data?.projects || []
  } finally {
    loading.value = false
  }
}

async function loadDashboard() {
  if (!workspaceId.value) return
  try {
    const res = await getDashboard(workspaceId.value)
    dashboard.value = res?.data || null
  } catch (e) {
    dashboard.value = null
  }
}

function refresh() {
  fetchGantt()
  loadDashboard()
}

function formatAmount(raw: string): string {
  const n = Number(raw)
  return Number.isFinite(n) ? n.toLocaleString() : raw
}

const kpis = computed(() => {
  const d = dashboard.value
  return [
    {
      key: 'inFlight',
      label: t('views.finance.progressPage.kpi.inFlight'),
      value: d ? String(d.in_flight_count) : '—',
      hint: d
        ? t('views.finance.progressPage.kpi.inFlightHint', { total: d.total_count })
        : '',
      tone: 'normal',
    },
    {
      key: 'amount',
      label: t('views.finance.progressPage.kpi.inFlightAmount'),
      value: d ? formatAmount(d.in_flight_amount) : '—',
      hint: '',
      tone: 'normal',
    },
    {
      key: 'cycle',
      label: t('views.finance.progressPage.kpi.avgCycle'),
      value:
        d && d.avg_cycle_days !== null
          ? `${d.avg_cycle_days} ${t('views.finance.progressPage.kpi.avgCycleUnit')}`
          : '—',
      hint: '',
      tone: 'normal',
    },
    {
      key: 'passRate',
      label: t('views.finance.progressPage.kpi.passRate'),
      value: d && d.pass_rate !== null ? `${d.pass_rate}%` : '—',
      hint: '',
      tone: 'positive',
    },
    {
      key: 'risk',
      label: t('views.finance.progressPage.kpi.risk'),
      value: d ? String(d.risk.red + d.risk.yellow) : '—',
      hint: d
        ? t('views.finance.progressPage.kpi.riskHint', {
            red: d.risk.red,
            yellow: d.risk.yellow,
          })
        : '',
      tone: d && d.risk.red > 0 ? 'danger' : d && d.risk.yellow > 0 ? 'warn' : 'normal',
    },
  ]
})

async function loadOwners() {
  try {
    const res: any = await UserApi.getUserList({})
    ownerOptions.value = Array.isArray(res?.data)
      ? res.data.map((u: any) => ({
          label: u.nick_name || u.username || String(u.id),
          value: String(u.id),
        }))
      : []
  } catch (e) {
    ownerOptions.value = []
  }
}

function onSelect(p: GanttProject) {
  selectedProject.value = p
  drawerVisible.value = true
}

onMounted(() => {
  loadOwners()
  fetchGantt()
  loadDashboard()
})
</script>

<style lang="scss" scoped>
.finance-progress {
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

  &__legend {
    display: flex;
    gap: 14px;
    margin-left: auto;
  }

  &__legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__dot {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    display: inline-block;

    &.is-done {
      background: var(--el-color-success);
    }
    &.is-active {
      background: var(--el-color-primary);
    }
    &.is-pending {
      background: var(--el-fill-color-darker);
    }
    &.is-skipped {
      background: var(--el-color-info-light-5);
    }
  }

  &__kpis {
    display: flex;
    gap: 12px;
  }

  &__kpi {
    flex: 1;
    padding: 12px 16px;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 6px;
    background: var(--el-bg-color);
  }

  &__kpi-label {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }

  &__kpi-value {
    margin-top: 6px;
    font-size: 24px;
    font-weight: 600;
    color: var(--el-text-color-primary);

    &.is-warn {
      color: var(--el-color-warning);
    }
    &.is-danger {
      color: var(--el-color-danger);
    }
    &.is-positive {
      color: var(--el-color-success);
    }
  }

  &__kpi-hint {
    margin-top: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}
</style>

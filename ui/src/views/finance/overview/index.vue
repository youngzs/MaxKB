<template>
  <!--
    Finance overview / dashboard.
    Top: live KPI cards (in-flight projects, pending reviews, recent sends,
    docs generated). Middle: P1 module shortcuts. Bottom: links to the
    "coming soon" rich docs for P2 / P3 so users can read what's planned.
    KPI counts come from existing list APIs (using `size: 1` so we get
    `total` cheaply); failures degrade silently to "-".
  -->
  <div class="finance-overview p-24">
    <div class="finance-overview__header mb-24">
      <h2 class="finance-overview__title">{{ $t('views.finance.overview') }}</h2>
      <p class="finance-overview__desc">{{ $t('views.finance.overviewDesc') }}</p>
    </div>

    <!-- KPI strip -->
    <div class="finance-overview__kpis">
      <div
        v-for="kpi in kpis"
        :key="kpi.key"
        class="finance-overview__kpi"
        @click="kpi.path && goTo(kpi.path)"
      >
        <div class="finance-overview__kpi-label">
          {{ $t(kpi.labelKey) }}
        </div>
        <div class="finance-overview__kpi-value" :class="`is-${kpi.tone}`">
          <template v-if="kpi.loading">
            <AppIcon iconName="app-loading" />
          </template>
          <template v-else-if="kpi.value === null">—</template>
          <template v-else>{{ kpi.value }}</template>
        </div>
        <div v-if="kpi.hintKey" class="finance-overview__kpi-hint">
          {{ $t(kpi.hintKey) }}
        </div>
      </div>
    </div>

    <!-- P1 module entry cards -->
    <h3 class="finance-overview__section-title">
      {{ $t('views.finance.overviewSections.entries') }}
    </h3>
    <div class="finance-overview__grid">
      <el-card
        v-for="card in entryCards"
        :key="card.key"
        class="finance-overview__card"
        shadow="hover"
        @click="goTo(card.path)"
      >
        <div class="finance-overview__card-body">
          <div class="finance-overview__icon">{{ card.icon }}</div>
          <h3 class="finance-overview__card-title">{{ $t(card.titleKey) }}</h3>
          <p class="finance-overview__card-desc">{{ $t(card.descKey) }}</p>
          <div class="finance-overview__card-footer">
            <el-button type="primary" text>
              {{ $t('views.finance.action.enter') }}
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <!-- Planning / coming-soon section -->
    <h3 class="finance-overview__section-title">
      {{ $t('views.finance.overviewSections.planning') }}
    </h3>
    <p class="finance-overview__section-desc">
      {{ $t('views.finance.overviewSections.planningDesc') }}
    </p>
    <div class="finance-overview__grid">
      <el-card
        v-for="card in planningCards"
        :key="card.key"
        class="finance-overview__card finance-overview__card--planning"
        shadow="hover"
        @click="goTo(card.path)"
      >
        <div class="finance-overview__card-body">
          <div class="finance-overview__icon">{{ card.icon }}</div>
          <div class="finance-overview__planning-tag">
            <el-tag
              :type="card.phase === 'P3' ? 'info' : 'warning'"
              effect="plain"
              size="small"
            >
              {{ card.phase }} · {{ $t('views.finance.planning') }}
            </el-tag>
          </div>
          <h3 class="finance-overview__card-title">{{ $t(card.titleKey) }}</h3>
          <p class="finance-overview__card-desc">{{ $t(card.descKey) }}</p>
          <div class="finance-overview__card-footer">
            <el-button type="info" text>
              {{ $t('views.finance.overviewSections.viewPlan') }}
            </el-button>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import useStore from '@/stores'
import { listProjects } from '@/api/finance/project'
import { listTasks as listMaterialsTasks } from '@/api/finance/materials-task'
import { listGenerations } from '@/api/finance/generation'
import { listAuditLog } from '@/api/finance/audit-log'
import type { AuditAction, ProjectStatus } from '@/api/finance/type'

interface Kpi {
  key: string
  labelKey: string
  hintKey?: string
  value: number | null
  loading: boolean
  tone: 'normal' | 'warn' | 'positive'
  path?: string
}

const router = useRouter()
const { user } = useStore()

const kpis = ref<Kpi[]>([
  {
    key: 'inFlight',
    labelKey: 'views.finance.overviewKpis.inFlight',
    hintKey: 'views.finance.overviewKpis.inFlightHint',
    value: null,
    loading: true,
    tone: 'normal',
    path: '/finance/project',
  },
  {
    key: 'pendingReview',
    labelKey: 'views.finance.overviewKpis.pendingReview',
    hintKey: 'views.finance.overviewKpis.pendingReviewHint',
    value: null,
    loading: true,
    tone: 'warn',
    path: '/finance/materials',
  },
  {
    key: 'docsTotal',
    labelKey: 'views.finance.overviewKpis.docsTotal',
    hintKey: 'views.finance.overviewKpis.docsTotalHint',
    value: null,
    loading: true,
    tone: 'positive',
    path: '/finance/documents',
  },
  {
    key: 'sendsRecent',
    labelKey: 'views.finance.overviewKpis.sendsRecent',
    hintKey: 'views.finance.overviewKpis.sendsRecentHint',
    value: null,
    loading: true,
    tone: 'normal',
    path: '/finance/audit',
  },
])

const entryCards = [
  {
    key: 'project',
    icon: '📂',
    titleKey: 'views.finance.cards.project.title',
    descKey: 'views.finance.cards.project.desc',
    path: '/finance/project',
  },
  {
    key: 'materials',
    icon: '📝',
    titleKey: 'views.finance.cards.materials.title',
    descKey: 'views.finance.cards.materials.desc',
    path: '/finance/materials',
  },
  {
    key: 'documents',
    icon: '📄',
    titleKey: 'views.finance.cards.documents.title',
    descKey: 'views.finance.cards.documents.desc',
    path: '/finance/documents',
  },
]

const planningCards = [
  {
    key: 'feasibility',
    phase: 'P2' as const,
    icon: '🔍',
    titleKey: 'views.finance.cards.feasibility.title',
    descKey: 'views.finance.cards.feasibility.desc',
    path: '/finance/feasibility',
  },
  {
    key: 'progress',
    phase: 'P2' as const,
    icon: '📈',
    titleKey: 'views.finance.cards.progress.title',
    descKey: 'views.finance.cards.progress.desc',
    path: '/finance/progress',
  },
  {
    key: 'intel',
    phase: 'P3' as const,
    icon: '📡',
    titleKey: 'views.finance.cards.intel.title',
    descKey: 'views.finance.cards.intel.desc',
    path: '/finance/intel',
  },
]

function goTo(path: string) {
  router.push(path)
}

function setKpi(key: string, value: number | null) {
  const k = kpis.value.find((it) => it.key === key)
  if (!k) return
  k.value = value
  k.loading = false
}

const isoOfDaysAgo = (days: number): string => {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(0, 0, 0, 0)
  return d.toISOString()
}

async function refresh() {
  const wid = user.getWorkspaceId()
  if (!wid) return

  // Use size:1 to fetch just the `total` count for each filter. Each call
  // is independent — a 403 or 5xx on one degrades to "—" without blocking
  // the others. We deliberately do not Promise.all so a slow audit-log
  // query doesn't block the fast project list.
  // "In-flight" is approximated as projects in the engaging stage; refine
  // when the backend grows a multi-status filter (today it accepts a
  // single status only).
  const inFlightStatus: ProjectStatus = 'engaging'
  listProjects(wid, { size: 1, status: inFlightStatus })
    .then((res) => setKpi('inFlight', res?.data?.total ?? 0))
    .catch(() => setKpi('inFlight', null))

  listMaterialsTasks(wid, { size: 1, status: 'pending_review' })
    .then((res) => setKpi('pendingReview', res?.data?.total ?? 0))
    .catch(() => setKpi('pendingReview', null))

  listGenerations(wid, { size: 1 })
    .then((res) => setKpi('docsTotal', res?.data?.total ?? 0))
    .catch(() => setKpi('docsTotal', null))

  const sendAction: AuditAction = 'SEND'
  listAuditLog(wid, {
    size: 1,
    action: sendAction,
    date_from: isoOfDaysAgo(7),
  })
    .then((res) => setKpi('sendsRecent', res?.data?.total ?? 0))
    .catch(() => setKpi('sendsRecent', null))
}

onMounted(() => {
  refresh()
})
</script>

<style lang="scss" scoped>
.finance-overview {
  &__header {
    margin-bottom: 24px;
  }

  &__title {
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 8px;
    color: var(--el-text-color-primary);
  }

  &__desc {
    margin: 0;
    color: var(--el-text-color-regular);
    font-size: 14px;
  }

  &__kpis {
    display: grid;
    grid-template-columns: repeat(1, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 28px;

    @media (min-width: 640px) {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    @media (min-width: 1024px) {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
  }

  &__kpi {
    padding: 16px 18px;
    border-radius: 8px;
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-light);
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;

    &:hover {
      transform: translateY(-1px);
      box-shadow: var(--el-box-shadow-light);
    }
  }

  &__kpi-label {
    font-size: 13px;
    color: var(--el-text-color-regular);
    margin-bottom: 8px;
  }

  &__kpi-value {
    font-size: 26px;
    font-weight: 600;
    line-height: 1.2;
    color: var(--el-text-color-primary);

    &.is-warn {
      color: var(--el-color-warning);
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

  &__section-title {
    font-size: 16px;
    font-weight: 600;
    margin: 12px 0 6px;
    color: var(--el-text-color-primary);
  }

  &__section-desc {
    margin: 0 0 14px;
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(1, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 28px;

    @media (min-width: 640px) {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    @media (min-width: 1024px) {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  &__card {
    cursor: pointer;
    transition: transform 0.2s ease;

    &--planning {
      background: var(--el-fill-color-lighter);
    }
  }

  &__card-body {
    display: flex;
    flex-direction: column;
    min-height: 160px;
    position: relative;
  }

  &__planning-tag {
    position: absolute;
    top: 0;
    right: 0;
  }

  &__icon {
    font-size: 28px;
    line-height: 1;
    margin-bottom: 12px;
  }

  &__card-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 8px;
    color: var(--el-text-color-primary);
  }

  &__card-desc {
    flex: 1;
    margin: 0 0 16px;
    color: var(--el-text-color-regular);
    font-size: 13px;
    line-height: 1.5;
  }

  &__card-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
  }
}
</style>

<template>
  <el-drawer
    v-model="innerVisible"
    :title="$t('views.finance.progressPage.alertsTitle')"
    direction="rtl"
    size="520px"
    @open="onOpen"
  >
    <div v-loading="loading" class="pad">
      <div v-if="!loading && alerts.length === 0" class="pad__empty">
        {{ $t('views.finance.progressPage.alertsEmpty') }}
      </div>

      <div
        v-for="a in alerts"
        :key="a.project_id"
        class="pad__item"
        :class="'is-' + a.risk"
      >
        <div class="pad__top">
          <span class="pad__name">{{ a.project_name }}</span>
          <el-tag
            size="small"
            :type="a.risk === 'red' ? 'danger' : 'warning'"
            disable-transitions
          >
            {{ $t('views.finance.progressPage.risk.' + a.risk) }}
          </el-tag>
        </div>
        <div class="pad__meta">
          <span>{{ $t('views.finance.project.projectType.' + a.project_type) }}</span>
          <span>
            {{ $t('views.finance.progressPage.owner') }}：{{ ownerName(a.owner_id) }}
          </span>
        </div>
        <div class="pad__meta">
          <span>
            {{ $t('views.finance.progressPage.activeStage') }}：{{ a.active_stage_label || '—' }}
          </span>
          <span v-if="a.active_planned_at">
            {{ $t('views.finance.progressPage.plannedAt') }}：{{ fmtDate(a.active_planned_at) }}
          </span>
        </div>
        <ul class="pad__reasons">
          <li v-for="code in a.risk_reasons" :key="code">
            {{ $t('views.finance.progressPage.risk.' + code) }}
          </li>
        </ul>
        <div class="pad__actions">
          <el-button link type="primary" size="small" @click="onView(a)">
            {{ $t('views.finance.progressPage.viewProject') }}
          </el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AlertItem } from '@/api/finance/type'
import { getAlerts } from '@/api/finance/progress'

const props = defineProps<{
  visible: boolean
  workspaceId: string
  ownerNameMap: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'select', projectId: string): void
}>()

const innerVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const loading = ref(false)
const alerts = ref<AlertItem[]>([])

function ownerName(id: string | null): string {
  if (!id) return '—'
  return props.ownerNameMap[id] || '—'
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function onOpen() {
  if (!props.workspaceId) return
  loading.value = true
  try {
    const res = await getAlerts(props.workspaceId)
    alerts.value = res?.data?.alerts || []
  } finally {
    loading.value = false
  }
}

function onView(a: AlertItem) {
  emit('select', a.project_id)
}
</script>

<style lang="scss" scoped>
.pad {
  min-height: 120px;

  &__empty {
    padding: 48px 0;
    text-align: center;
    color: var(--el-text-color-secondary);
  }

  &__item {
    padding: 12px;
    margin-bottom: 10px;
    border: 1px solid var(--el-border-color-lighter);
    border-left-width: 3px;
    border-radius: 6px;

    &.is-red {
      border-left-color: var(--el-color-danger);
    }
    &.is-yellow {
      border-left-color: var(--el-color-warning);
    }
  }

  &__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__name {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__meta {
    margin-top: 6px;
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__reasons {
    margin: 8px 0 0;
    padding-left: 18px;
    font-size: 12px;
    color: var(--el-color-danger);

    li {
      margin-bottom: 2px;
    }
  }

  &__actions {
    margin-top: 4px;
    text-align: right;
  }
}
</style>

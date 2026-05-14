<template>
  <el-drawer
    v-model="visibleInner"
    :title="$t('views.finance.workflowRun.title')"
    direction="rtl"
    size="640px"
    @open="onOpen"
    @close="onClose"
  >
    <div class="finance-workflow-run-drawer">
      <div class="finance-workflow-run-drawer__toolbar">
        <span class="finance-workflow-run-drawer__count">
          {{
            $t('views.finance.workflowRun.totalCount', {
              n: total,
            })
          }}
        </span>
        <el-button link size="small" :disabled="loading" @click="loadRuns">
          <AppIcon iconName="app-refresh" class="mr-4" />
          {{ $t('views.finance.workflowRun.refresh') }}
        </el-button>
        <el-switch
          v-model="autoRefresh"
          :active-text="$t('views.finance.workflowRun.autoRefresh')"
          size="small"
          style="margin-left: 12px"
        />
      </div>

      <el-table
        v-loading="loading"
        :data="runs"
        size="small"
        stripe
        style="width: 100%"
      >
        <el-table-column
          :label="$t('views.finance.workflowRun.columns.task')"
          min-width="180"
        >
          <template #default="{ row }">
            <code style="font-size: 12px">{{ row.task_name }}</code>
          </template>
        </el-table-column>

        <el-table-column
          :label="$t('views.finance.workflowRun.columns.status')"
          width="100"
        >
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" disable-transitions effect="plain">
              {{
                $t(`views.finance.workflowRun.status.${row.status}`, row.status)
              }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
          :label="$t('views.finance.workflowRun.columns.startedAt')"
          width="160"
        >
          <template #default="{ row }">
            {{ formatTime(row.started_at) || '-' }}
          </template>
        </el-table-column>

        <el-table-column
          :label="$t('views.finance.workflowRun.columns.duration')"
          width="100"
        >
          <template #default="{ row }">
            <span v-if="row.duration_ms != null">
              {{ (row.duration_ms / 1000).toFixed(1) }}s
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column
          :label="$t('views.finance.workflowRun.columns.retries')"
          width="70"
        >
          <template #default="{ row }">
            {{ row.retry_count }}
          </template>
        </el-table-column>

        <el-table-column
          :label="$t('views.finance.workflowRun.columns.error')"
          min-width="180"
        >
          <template #default="{ row }">
            <el-tooltip
              v-if="row.error_message"
              :content="row.error_message"
              placement="top"
            >
              <span
                style="
                  display: inline-block;
                  max-width: 220px;
                  overflow: hidden;
                  text-overflow: ellipsis;
                  white-space: nowrap;
                  color: var(--el-color-danger);
                "
              >
                {{ row.error_message }}
              </span>
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && runs.length === 0" class="finance-workflow-run-drawer__empty">
        {{ $t('views.finance.workflowRun.empty') }}
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  listWorkflowRuns,
  type WorkflowRun,
  type WorkflowRunStatus,
  type WorkflowRunTargetType,
} from '@/api/finance/workflow-run'

const props = defineProps<{
  visible: boolean
  workspaceId: string
  targetType: WorkflowRunTargetType
  targetId: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
}>()

const visibleInner = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const loading = ref(false)
const runs = ref<WorkflowRun[]>([])
const total = ref(0)
const autoRefresh = ref(true)
let timer: ReturnType<typeof setInterval> | null = null

const formatTime = (s: string | null) => {
  if (!s) return ''
  try {
    const d = new Date(s)
    if (isNaN(d.getTime())) return s
    return d.toLocaleString()
  } catch {
    return s
  }
}

const statusTagType = (s: WorkflowRunStatus) => {
  switch (s) {
    case 'queued':
      return 'info'
    case 'running':
      return 'primary'
    case 'succeeded':
      return 'success'
    case 'failed':
      return 'danger'
    case 'retrying':
      return 'warning'
    default:
      return ''
  }
}

const loadRuns = async () => {
  if (!props.workspaceId || !props.targetId) return
  loading.value = true
  try {
    const res = await listWorkflowRuns(props.workspaceId, {
      target_type: props.targetType,
      target_id: props.targetId,
      page: 1,
      size: 50,
    })
    const page = res?.data
    if (page) {
      runs.value = page.records || []
      total.value = page.total || runs.value.length
    }
  } catch {
    // swallow — drawer is a diagnostic, not load-bearing
  } finally {
    loading.value = false
  }
}

const startTimer = () => {
  stopTimer()
  if (!autoRefresh.value) return
  timer = setInterval(() => {
    if (!visibleInner.value) return
    loadRuns()
  }, 4000)
}

const stopTimer = () => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

const onOpen = () => {
  loadRuns()
  startTimer()
}

const onClose = () => {
  stopTimer()
}

watch(autoRefresh, () => {
  if (visibleInner.value && autoRefresh.value) startTimer()
  else stopTimer()
})

watch(
  () => props.targetId,
  () => {
    if (visibleInner.value) loadRuns()
  },
)

onBeforeUnmount(() => {
  stopTimer()
})
</script>

<style scoped>
.finance-workflow-run-drawer {
  padding: 0 16px 16px 16px;
}
.finance-workflow-run-drawer__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0 12px 0;
}
.finance-workflow-run-drawer__count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex: 1;
}
.finance-workflow-run-drawer__empty {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 32px 0;
  font-size: 13px;
}
</style>

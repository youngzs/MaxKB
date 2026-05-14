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
        row-key="id"
        style="width: 100%"
      >
        <!--
          Gate 8 Track C — per-row expansion: DISPLAY only.
          Surfaces engine / node-level progress / IO summary parsed from
          WorkflowRun.payload. The retry/cancel action buttons live in
          the fixed "actions" column below (Track B) — do not move logic
          between the two areas.
        -->
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="finance-workflow-run-detail">
              <template v-if="hasDetail(row)">
                <!-- engine badge -->
                <div class="finance-workflow-run-detail__line">
                  <span class="finance-workflow-run-detail__label">
                    {{ $t('views.finance.workflowRun.engine') }}
                  </span>
                  <el-tag size="small" effect="plain" disable-transitions>
                    {{ engineOf(row) }}
                  </el-tag>
                </div>

                <!-- node-level progress (workflow engine only) -->
                <div
                  v-if="nodesOf(row).length > 0"
                  class="finance-workflow-run-detail__line finance-workflow-run-detail__line--block"
                >
                  <span class="finance-workflow-run-detail__label">
                    {{ $t('views.finance.workflowRun.nodeProgress') }}
                  </span>
                  <ul class="finance-workflow-run-detail__nodes">
                    <li
                      v-for="(node, idx) in nodesOf(row)"
                      :key="node.id || node.name || idx"
                      class="finance-workflow-run-detail__node"
                    >
                      <el-tag
                        :type="nodeStatusTagType(node.status)"
                        size="small"
                        effect="plain"
                        disable-transitions
                      >
                        {{
                          $t(
                            `views.finance.workflowRun.status.${node.status}`,
                            node.status || '-',
                          )
                        }}
                      </el-tag>
                      <span class="finance-workflow-run-detail__node-name">
                        {{ node.name || node.id || `#${idx + 1}` }}
                      </span>
                      <span
                        v-if="node.duration_ms != null"
                        class="finance-workflow-run-detail__node-dur"
                      >
                        {{ (node.duration_ms / 1000).toFixed(1) }}s
                      </span>
                    </li>
                  </ul>
                </div>

                <!-- inputs summary -->
                <div
                  v-if="summaryEntries(row, 'inputs_summary').length > 0"
                  class="finance-workflow-run-detail__line finance-workflow-run-detail__line--block"
                >
                  <span class="finance-workflow-run-detail__label">
                    {{ $t('views.finance.workflowRun.inputsSummary') }}
                  </span>
                  <ul class="finance-workflow-run-detail__kv">
                    <li
                      v-for="kv in summaryEntries(row, 'inputs_summary')"
                      :key="kv.k"
                    >
                      <code>{{ kv.k }}</code>: {{ kv.v }}
                    </li>
                  </ul>
                </div>

                <!-- outputs summary -->
                <div
                  v-if="summaryEntries(row, 'output_summary').length > 0"
                  class="finance-workflow-run-detail__line finance-workflow-run-detail__line--block"
                >
                  <span class="finance-workflow-run-detail__label">
                    {{ $t('views.finance.workflowRun.outputsSummary') }}
                  </span>
                  <ul class="finance-workflow-run-detail__kv">
                    <li
                      v-for="kv in summaryEntries(row, 'output_summary')"
                      :key="kv.k"
                    >
                      <code>{{ kv.k }}</code>: {{ kv.v }}
                    </li>
                  </ul>
                </div>

                <!-- raw payload fallback (Gate 7 Track C component) -->
                <el-collapse class="finance-workflow-run-detail__raw">
                  <el-collapse-item
                    :title="$t('views.finance.workflowRun.title')"
                    name="raw"
                  >
                    <JsonPayload :value="row.payload" max-height="240px" />
                  </el-collapse-item>
                </el-collapse>
              </template>

              <div v-else class="finance-workflow-run-detail__none">
                {{ $t('views.finance.workflowRun.noDetail') }}
              </div>
            </div>
          </template>
        </el-table-column>

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
          width="130"
        >
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" disable-transitions effect="plain">
              {{
                $t(`views.finance.workflowRun.status.${row.status}`, row.status)
              }}
            </el-tag>
            <el-tooltip
              v-if="isStale(row)"
              :content="$t('views.finance.workflowRun.staleHint')"
              placement="top"
            >
              <el-tag
                type="warning"
                size="small"
                effect="dark"
                disable-transitions
                style="margin-top: 2px"
              >
                {{ $t('views.finance.workflowRun.staleBadge') }}
              </el-tag>
            </el-tooltip>
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

        <el-table-column
          :label="$t('views.finance.workflowRun.columns.actions')"
          width="92"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              v-if="canRetry(row.status)"
              link
              type="primary"
              size="small"
              :loading="actionRunId === row.id"
              :disabled="actionRunId !== null"
              @click="onRetry(row)"
            >
              {{ $t('views.finance.workflowRun.retry') }}
            </el-button>
            <el-button
              v-else-if="canCancel(row.status)"
              link
              type="danger"
              size="small"
              :loading="actionRunId === row.id"
              :disabled="actionRunId !== null"
              @click="onCancel(row)"
            >
              {{ $t('views.finance.workflowRun.cancel') }}
            </el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { t } from '@/locales'
import {
  cancelWorkflowRun,
  listWorkflowRuns,
  retryWorkflowRun,
  type WorkflowRun,
  type WorkflowRunStatus,
  type WorkflowRunTargetType,
} from '@/api/finance/workflow-run'
import JsonPayload from './JsonPayload.vue'

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
// id of the run whose retry/cancel call is in flight (null = idle). Used to
// show a spinner on the acting button and disable the rest.
const actionRunId = ref<string | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

// A run sitting in queued/running with started_at (or created_at, for rows
// the worker never picked up) older than this is flagged "可能已卡住".
const STALE_AFTER_MS = 15 * 60 * 1000

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
    case 'cancelled':
      return 'info'
    default:
      return ''
  }
}

// ---- Gate 8 Track C: row-expansion DISPLAY helpers ----------------------
// These parse WorkflowRun.payload (populated by Gate 8 Track A) defensively:
// the shape is not guaranteed, so every accessor tolerates missing / wrong
// types and degrades to an empty value rather than throwing in the template.

interface WorkflowNodeDetail {
  id?: string
  name?: string
  status?: WorkflowRunStatus | string
  duration_ms?: number | null
}

const payloadOf = (row: WorkflowRun): Record<string, unknown> => {
  const p = row?.payload
  return p && typeof p === 'object' && !Array.isArray(p)
    ? (p as Record<string, unknown>)
    : {}
}

// 'workflow' when the run went through the graph engine, else 'direct'.
// We trust an explicit payload.engine, otherwise infer from node presence.
const engineOf = (row: WorkflowRun): string => {
  const p = payloadOf(row)
  const explicit = p.engine
  if (typeof explicit === 'string' && explicit) return explicit
  return nodesOf(row).length > 0 ? 'workflow' : 'direct'
}

const nodesOf = (row: WorkflowRun): WorkflowNodeDetail[] => {
  const nodes = payloadOf(row).nodes
  if (!Array.isArray(nodes)) return []
  return nodes
    .filter((n): n is Record<string, unknown> => !!n && typeof n === 'object')
    .map((n) => ({
      id: typeof n.id === 'string' ? n.id : undefined,
      name: typeof n.name === 'string' ? n.name : undefined,
      status: typeof n.status === 'string' ? n.status : undefined,
      duration_ms: typeof n.duration_ms === 'number' ? n.duration_ms : null,
    }))
}

// Flatten a {inputs_summary|output_summary} sub-object into a printable
// key/value list. Non-object summaries (or absent ones) yield [].
const summaryEntries = (
  row: WorkflowRun,
  key: 'inputs_summary' | 'output_summary',
): Array<{ k: string; v: string }> => {
  const raw = payloadOf(row)[key]
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return []
  return Object.entries(raw as Record<string, unknown>).map(([k, v]) => ({
    k,
    v:
      v === null || v === undefined
        ? '-'
        : typeof v === 'object'
          ? JSON.stringify(v)
          : String(v),
  }))
}

// Tag colour for a node status. Node statuses come from a free-form
// payload, so this tolerates undefined / unknown strings (falls through
// to the neutral default) — unlike statusTagType which is typed to the
// closed WorkflowRunStatus union used by the run rows themselves.
const nodeStatusTagType = (s: string | undefined) =>
  s ? statusTagType(s as WorkflowRunStatus) : ''

// True when the payload carries anything worth expanding for. An empty
// payload (or one with no node / summary detail) shows the graceful
// "no detail" message instead.
const hasDetail = (row: WorkflowRun): boolean => {
  const p = payloadOf(row)
  if (Object.keys(p).length === 0) return false
  return (
    nodesOf(row).length > 0 ||
    summaryEntries(row, 'inputs_summary').length > 0 ||
    summaryEntries(row, 'output_summary').length > 0 ||
    typeof p.engine === 'string'
  )
}

// failed / cancelled runs can be re-dispatched.
const canRetry = (s: WorkflowRunStatus) => s === 'failed' || s === 'cancelled'
// in-flight runs can be cancelled.
const canCancel = (s: WorkflowRunStatus) =>
  s === 'running' || s === 'queued' || s === 'retrying'

// Client-side stale detection — mirrors the backend's find_stale_runs
// 15-minute threshold. Anchored on started_at, falling back to created_at
// for rows still queued (never picked up by a worker).
const isStale = (row: WorkflowRun) => {
  if (!canCancel(row.status)) return false
  const anchorRaw = row.started_at || row.created_at
  if (!anchorRaw) return false
  const anchor = new Date(anchorRaw).getTime()
  if (isNaN(anchor)) return false
  return Date.now() - anchor > STALE_AFTER_MS
}

const onRetry = async (row: WorkflowRun) => {
  if (actionRunId.value) return
  actionRunId.value = row.id
  try {
    await retryWorkflowRun(props.workspaceId, row.id)
    ElMessage.success(t('views.finance.workflowRun.retrySuccess'))
    await loadRuns()
  } catch {
    ElMessage.error(t('views.finance.workflowRun.retryFailed'))
  } finally {
    actionRunId.value = null
  }
}

const onCancel = async (row: WorkflowRun) => {
  if (actionRunId.value) return
  try {
    await ElMessageBox.confirm(
      t('views.finance.workflowRun.cancelConfirm'),
      t('views.finance.workflowRun.cancel'),
      {
        type: 'warning',
        confirmButtonText: t('views.finance.workflowRun.cancel'),
        cancelButtonText: t('views.finance.workflowRun.cancelDismiss'),
      },
    )
  } catch {
    // user dismissed the confirm dialog — nothing to do.
    return
  }
  actionRunId.value = row.id
  try {
    await cancelWorkflowRun(props.workspaceId, row.id)
    ElMessage.success(t('views.finance.workflowRun.cancelSuccess'))
    await loadRuns()
  } catch {
    ElMessage.error(t('views.finance.workflowRun.cancelFailed'))
  } finally {
    actionRunId.value = null
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

/* ---- Gate 8 Track C: row-expansion detail area ---- */
.finance-workflow-run-detail {
  padding: 8px 16px 4px 48px;
  font-size: 12px;
}
.finance-workflow-run-detail__line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.finance-workflow-run-detail__line--block {
  display: block;
}
.finance-workflow-run-detail__label {
  color: var(--el-text-color-secondary);
  font-weight: 600;
}
.finance-workflow-run-detail__nodes,
.finance-workflow-run-detail__kv {
  list-style: none;
  margin: 6px 0 0 0;
  padding: 0;
}
.finance-workflow-run-detail__node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}
.finance-workflow-run-detail__node-name {
  color: var(--el-text-color-primary);
}
.finance-workflow-run-detail__node-dur {
  color: var(--el-text-color-secondary);
  margin-left: auto;
}
.finance-workflow-run-detail__kv li {
  padding: 1px 0;
  color: var(--el-text-color-primary);
}
.finance-workflow-run-detail__kv code {
  color: var(--el-color-primary);
}
.finance-workflow-run-detail__raw {
  margin-top: 4px;
}
.finance-workflow-run-detail__none {
  color: var(--el-text-color-secondary);
  padding: 8px 0;
}
</style>

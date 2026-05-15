<template>
  <div class="finance-materials-detail" v-loading="loading">
    <!-- Header / breadcrumb / actions -->
    <div class="finance-materials-detail__header p-24">
      <div class="flex" style="align-items: center; gap: 12px">
        <el-button link @click="goBack">
          <AppIcon iconName="app-arrow-left" class="mr-4" />
          {{ $t('views.finance.materials.detail.backToList') }}
        </el-button>
        <h2 class="finance-materials-detail__title" v-if="task">
          {{ task.title }}
        </h2>
        <el-tag
          v-if="task"
          :type="statusTagType(task.status)"
          disable-transitions
          effect="plain"
        >
          <AppIcon
            v-if="isTransient(task.status)"
            iconName="app-loading"
            class="mr-4"
            style="vertical-align: middle"
          />
          {{ $t(`views.finance.materials.status.${task.status}`) }}
        </el-tag>
        <span class="finance-materials-detail__project" v-if="task">
          {{ projectName }}
        </span>
      </div>

      <div
        class="finance-materials-detail__actions flex"
        v-if="task"
        style="gap: 8px; align-items: center"
      >
        <el-button
          v-if="canEdit"
          :disabled="!canReparse"
          @click="onReparse"
        >
          {{ $t('views.finance.materials.detail.actions.reparse') }}
        </el-button>
        <el-button
          v-if="canEdit"
          :disabled="!canRematch"
          @click="onRematch"
        >
          {{ $t('views.finance.materials.detail.actions.rematch') }}
        </el-button>
        <el-button
          v-if="canEdit"
          :disabled="!canPack"
          @click="onPack"
        >
          {{ $t('views.finance.materials.detail.actions.pack') }}
        </el-button>
        <el-button
          v-if="canEdit"
          type="primary"
          :disabled="!canSubmit"
          @click="onSubmit"
        >
          {{ $t('views.finance.materials.detail.actions.submit') }}
        </el-button>
        <el-button
          v-if="canReview && task.status === 'pending_review'"
          type="success"
          @click="onApprove"
        >
          {{ $t('views.finance.materials.detail.actions.approve') }}
        </el-button>
        <el-button
          v-if="canReview && task.status === 'pending_review'"
          type="danger"
          @click="openRejectDialog"
        >
          {{ $t('views.finance.materials.detail.actions.reject') }}
        </el-button>
        <el-button
          :disabled="!canDownload"
          @click="onDownload"
        >
          {{ $t('views.finance.materials.detail.actions.download') }}
        </el-button>
        <el-button
          v-if="canSend && task.status === 'approved'"
          type="primary"
          @click="sendDialogVisible = true"
        >
          {{ $t('views.finance.send.actions.send') }}
        </el-button>
      </div>
    </div>

    <!-- Body -->
    <div v-if="task" class="finance-materials-detail__body">
      <!-- Transient (parsing / matching) overlay -->
      <div
        v-if="isTransient(task.status)"
        class="finance-materials-detail__progress"
      >
        <AppIcon
          iconName="app-loading"
          class="finance-materials-detail__spinner"
        />
        <p class="finance-materials-detail__progress-msg">
          {{
            task.status === 'parsing'
              ? $t('views.finance.materials.detail.parsingMessage')
              : $t('views.finance.materials.detail.matchingMessage')
          }}
        </p>
        <p class="finance-materials-detail__progress-hint">
          {{ $t('views.finance.materials.detail.progressHint') }}
        </p>
        <el-button
          link
          type="primary"
          size="small"
          @click="workflowRunDrawerVisible = true"
        >
          {{ $t('views.finance.workflowRun.openLogLink') }}
        </el-button>
      </div>

      <!-- Failed state -->
      <div
        v-else-if="task.status === 'failed'"
        class="finance-materials-detail__failed"
      >
        <el-card shadow="never" class="finance-materials-detail__failed-card">
          <template #header>
            <strong>
              {{ $t('views.finance.materials.detail.failedTitle') }}
            </strong>
          </template>
          <p class="finance-materials-detail__error-msg">
            {{ task.error_message || '-' }}
          </p>
          <div style="display: flex; gap: 8px">
            <el-button v-if="canEdit" type="primary" @click="onRetryLastStep">
              {{ $t('views.finance.materials.detail.retry') }}
            </el-button>
            <el-button
              link
              type="primary"
              @click="workflowRunDrawerVisible = true"
            >
              {{ $t('views.finance.workflowRun.openLogLink') }}
            </el-button>
          </div>
        </el-card>
      </div>

      <!-- Empty parsed_items in draft -->
      <div
        v-else-if="
          task.status === 'draft' &&
          (!task.parsed_items || task.parsed_items.length === 0)
        "
        class="finance-materials-detail__empty"
      >
        <p>
          {{ $t('views.finance.materials.detail.emptyParsedItems') }}
        </p>
        <el-button v-if="canEdit" type="primary" @click="onReparse">
          {{ $t('views.finance.materials.detail.actions.reparse') }}
        </el-button>
      </div>

      <!-- Three-pane workspace -->
      <div v-else class="finance-materials-detail__panes">
        <!-- Pane 1: requirement items -->
        <div class="finance-materials-detail__pane finance-materials-detail__pane--p1">
          <div class="finance-materials-detail__pane-header">
            {{ $t('views.finance.materials.detail.pane1Title') }}
          </div>
          <ul class="finance-materials-detail__items">
            <li
              v-for="item in task.parsed_items"
              :key="item.key"
              class="finance-materials-detail__item"
              :class="{
                'finance-materials-detail__item--active':
                  focusedItemKey === item.key,
              }"
              @click="focusedItemKey = item.key"
            >
              <span class="finance-materials-detail__item-label">
                {{ item.label }}
                <span
                  v-if="item.required"
                  class="finance-materials-detail__required"
                >
                  {{ $t('views.finance.materials.detail.requiredMark') }}
                </span>
              </span>
              <span
                v-if="itemSelectedCount[item.key]"
                class="finance-materials-detail__item-badge"
              >
                {{ itemSelectedCount[item.key] }}
              </span>
            </li>
          </ul>
        </div>

        <!-- Pane 2: matched documents -->
        <div class="finance-materials-detail__pane finance-materials-detail__pane--p2">
          <div class="finance-materials-detail__pane-header">
            {{ $t('views.finance.materials.detail.pane2Title') }}
          </div>
          <div class="finance-materials-detail__matched">
            <div
              v-if="matchedForFocused.length === 0"
              class="finance-materials-detail__matched-empty"
            >
              {{ $t('views.finance.materials.detail.emptyMatched') }}
            </div>
            <div
              v-for="doc in matchedForFocused"
              :key="doc.document_id"
              class="finance-materials-detail__doc-row"
              :class="{
                'finance-materials-detail__doc-row--locked': isLocked(doc),
                'finance-materials-detail__doc-row--active':
                  focusedDoc?.document_id === doc.document_id,
              }"
              @click="focusedDoc = doc"
            >
              <el-checkbox
                :model-value="selectedSet.has(doc.document_id)"
                :disabled="isLocked(doc) || !canEdit"
                @click.stop
                @change="(v: boolean) => toggleSelect(doc, v)"
              />
              <div class="finance-materials-detail__doc-info">
                <div class="finance-materials-detail__doc-name">
                  {{ doc.document_name }}
                  <span
                    v-if="isLocked(doc)"
                    class="finance-materials-detail__lock"
                  >
                    <el-tooltip
                      :content="
                        $t('views.finance.materials.detail.lockedTooltip')
                      "
                      placement="top"
                    >
                      <span>
                        <AppIcon iconName="app-lock" />
                        {{
                          $t('views.finance.materials.detail.lockedBadge')
                        }}
                      </span>
                    </el-tooltip>
                  </span>
                </div>
                <div class="finance-materials-detail__doc-meta">
                  <SensitivityBadge
                    :level="doc.sensitivity_level"
                    size="small"
                  />
                  <span class="finance-materials-detail__score">
                    {{ $t('views.finance.materials.detail.score') }}:
                    {{ formatScore(doc.score) }}
                  </span>
                </div>
                <div
                  v-if="doc.snippet"
                  class="finance-materials-detail__snippet"
                >
                  {{ doc.snippet }}
                </div>
              </div>
            </div>
            <div
              v-if="canEdit && focusedItemKey"
              class="finance-materials-detail__add-doc"
            >
              <el-button
                link
                type="primary"
                size="small"
                @click="manualPickerVisible = true"
              >
                {{ $t('views.finance.materials.detail.addDoc') }}
              </el-button>
            </div>
          </div>
        </div>

        <!-- Pane 3: summary -->
        <div class="finance-materials-detail__pane finance-materials-detail__pane--p3">
          <div class="finance-materials-detail__pane-header">
            {{ $t('views.finance.materials.detail.pane3Title') }}
          </div>
          <div
            v-if="!focusedDoc"
            class="finance-materials-detail__pane-empty"
          >
            {{ $t('views.finance.materials.detail.emptyDoc') }}
          </div>
          <div v-else class="finance-materials-detail__doc-detail">
            <div class="finance-materials-detail__doc-detail-name">
              {{ focusedDoc.document_name }}
            </div>
            <div class="finance-materials-detail__doc-detail-meta">
              <SensitivityBadge
                :level="focusedDoc.sensitivity_level"
                size="small"
              />
            </div>
            <div class="finance-materials-detail__summary">
              {{ focusedDoc.ai_summary || '-' }}
            </div>
            <div class="finance-materials-detail__doc-detail-actions">
              <el-button
                v-if="canEdit"
                size="small"
                :loading="summarizing"
                :disabled="summarizing"
                @click="onSummarize"
              >
                {{
                  summarizing
                    ? $t('views.finance.materials.detail.summarizeBusy')
                    : $t('views.finance.materials.detail.regenerateSummary')
                }}
              </el-button>
              <el-button
                size="small"
                link
                type="primary"
                @click="openInKnowledge(focusedDoc)"
              >
                {{ $t('views.finance.materials.detail.openInKnowledge') }}
              </el-button>
              <el-button
                v-if="canEdit && selectedSet.has(focusedDoc.document_id)"
                size="small"
                type="danger"
                link
                @click="toggleSelect(focusedDoc, false)"
              >
                {{ $t('views.finance.materials.detail.removeFromSelection') }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Reject dialog -->
    <el-dialog
      v-model="rejectDialogVisible"
      :title="$t('views.finance.materials.detail.rejectDialogTitle')"
      width="480"
      append-to-body
    >
      <el-form
        ref="rejectFormRef"
        :model="rejectForm"
        :rules="rejectRules"
        label-position="top"
      >
        <el-form-item
          :label="$t('views.finance.materials.detail.rejectReasonLabel')"
          prop="comment"
        >
          <el-input
            v-model="rejectForm.comment"
            type="textarea"
            :rows="4"
            :placeholder="
              $t('views.finance.materials.detail.rejectReasonPlaceholder')
            "
            maxlength="1000"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="rejectDialogVisible = false">
            {{ $t('common.cancel') }}
          </el-button>
          <el-button type="danger" @click="confirmReject">
            {{ $t('views.finance.materials.detail.actions.reject') }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Manual document picker drawer -->
    <el-drawer
      v-model="manualPickerVisible"
      :title="$t('views.finance.materials.detail.manualPicker.title')"
      direction="rtl"
      size="420px"
      append-to-body
    >
      <el-input
        v-model="pickerKeyword"
        :placeholder="
          $t('views.finance.materials.detail.manualPicker.searchPlaceholder')
        "
        clearable
        style="margin-bottom: 12px"
      />
      <div class="finance-materials-detail__picker-hint">
        {{ $t('views.finance.materials.detail.manualPicker.empty') }}
      </div>
    </el-drawer>

    <!-- Email send log panel (Gate 5 Track B) -->
    <div v-if="task" class="finance-materials-detail__sendlog">
      <el-collapse v-model="sendLogPanel">
        <el-collapse-item
          :title="$t('views.finance.send.log.title')"
          name="sendlog"
        >
          <el-table
            :data="sendLogs"
            empty-text=" "
            v-loading="sendLogLoading"
            size="small"
            style="width: 100%"
          >
            <el-table-column
              :label="$t('views.finance.send.log.columns.createdAt')"
              prop="created_at"
              min-width="160"
            />
            <el-table-column
              :label="$t('views.finance.send.log.columns.to')"
              min-width="220"
            >
              <template #default="{ row }">
                <span>{{ (row.to_addresses || []).join(', ') }}</span>
              </template>
            </el-table-column>
            <el-table-column
              :label="$t('views.finance.send.log.columns.subject')"
              prop="subject"
              min-width="220"
              show-overflow-tooltip
            />
            <el-table-column
              :label="$t('views.finance.send.log.columns.status')"
              width="120"
            >
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="sendStatusType(row.status)"
                >
                  {{ $t(`views.finance.send.log.status.${row.status}`) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              :label="$t('views.finance.send.log.columns.error')"
              min-width="220"
              show-overflow-tooltip
            >
              <template #default="{ row }">
                <span>{{ row.error_message || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
          <p v-if="sendLogs.length === 0 && !sendLogLoading"
            class="finance-materials-detail__sendlog-empty">
            {{ $t('views.finance.send.log.empty') }}
          </p>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- Send dialog (Gate 5 Track B) -->
    <SendMaterialsDialog
      v-model:visible="sendDialogVisible"
      :task="task"
      :project-name="projectName"
      @sent="onSent"
    />

    <!-- Workflow run drawer (Gate 7 Track B) -->
    <WorkflowRunDrawer
      v-if="task"
      v-model:visible="workflowRunDrawerVisible"
      :workspace-id="workspaceId"
      target-type="MATERIALS_TASK"
      :target-id="task.id"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { MsgConfirm, MsgError, MsgSuccess, MsgWarning } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import { downloadZip } from '@/api/finance/materials-task'
import { listEmailSendLogs } from '@/api/finance/email-send'
import type {
  EmailSendLog,
  EmailSendStatus,
  MatchedDocument,
  MaterialsTask,
  MaterialsTaskStatus,
  SensitivityLevel,
} from '@/api/finance/type'
import SensitivityBadge from '@/components/sensitivity-badge/index.vue'
import SendMaterialsDialog from './components/SendMaterialsDialog.vue'
import WorkflowRunDrawer from '../components/WorkflowRunDrawer.vue'

const route = useRoute()
const router = useRouter()
const {
  user,
  financeProject: projectStore,
  financeMaterials: store,
} = useStore()

const loading = ref(false)
const summarizing = ref(false)
const focusedItemKey = ref<string>('')
const focusedDoc = ref<MatchedDocument | null>(null)
const rejectDialogVisible = ref(false)
const rejectFormRef = ref<FormInstance>()
const rejectForm = ref({ comment: '' })
const manualPickerVisible = ref(false)
const pickerKeyword = ref('')
// Gate 7 Track B: workflow-run drawer + per-step progress.
const workflowRunDrawerVisible = ref(false)
const workspaceId = computed<string>(() => String(user.getWorkspaceId() || ''))

const TRANSIENT: MaterialsTaskStatus[] = ['parsing', 'matching']

const isTransient = (s: MaterialsTaskStatus): boolean => TRANSIENT.includes(s)

const task = computed<MaterialsTask | null>(() => store.selected)
const pk = computed<string>(() => String(route.params.pk || ''))

const projectName = computed(() => {
  if (!task.value) return ''
  return (
    projectStore.list.find((p) => p.id === task.value!.project_id)?.name ||
    task.value.project_id
  )
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

const canReview = computed(() =>
  hasPermission(
    [
      RoleConst.ADMIN,
      RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
      PermissionConst.FINANCE_REVIEW.getWorkspacePermission,
      PermissionConst.FINANCE_REVIEW.getWorkspacePermissionWorkspaceManageRole,
    ],
    'OR',
  ),
)

const canSend = computed(() =>
  hasPermission(
    [
      RoleConst.ADMIN,
      RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
      PermissionConst.FINANCE_SEND.getWorkspacePermission,
      PermissionConst.FINANCE_SEND.getWorkspacePermissionWorkspaceManageRole,
    ],
    'OR',
  ),
)

// ---- Send dialog + send log (Gate 5 Track B) ----
const sendDialogVisible = ref(false)
const sendLogPanel = ref<string[]>([])
const sendLogLoading = ref(false)
const sendLogs = ref<EmailSendLog[]>([])

const sendStatusType = (
  s: EmailSendStatus,
): 'info' | 'primary' | 'success' | 'warning' | 'danger' => {
  switch (s) {
    case 'sent':
      return 'success'
    case 'sending':
    case 'queued':
      return 'warning'
    case 'failed':
      return 'danger'
    case 'retried':
      return 'primary'
    default:
      return 'info'
  }
}

const fetchSendLogs = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  sendLogLoading.value = true
  try {
    const res = await listEmailSendLogs(wid, {
      target_type: 'MATERIALS_TASK',
      target_id: task.value.id,
      size: 50,
    })
    sendLogs.value = (res.data?.records as EmailSendLog[]) || []
  } finally {
    sendLogLoading.value = false
  }
}

const onSent = async () => {
  // After a successful send, refresh both the task (status flips to 'sent')
  // and the send-log table.
  await fetchTask()
  await fetchSendLogs()
}

/** Levels >= confidential are treated as locked for the current user.
 *  TODO: replace this with the real per-user clearance once the backend
 *  exposes it on the auth/profile endpoint. */
const LOCKED_LEVELS: SensitivityLevel[] = ['confidential', 'secret']
const isLocked = (doc: MatchedDocument): boolean =>
  LOCKED_LEVELS.includes(doc.sensitivity_level)

const selectedSet = computed<Set<string>>(
  () => new Set(task.value?.selected_documents || []),
)

const matchedForFocused = computed<MatchedDocument[]>(() => {
  if (!task.value || !focusedItemKey.value) return []
  return (task.value.matched_documents || []).filter(
    (d) => d.item_key === focusedItemKey.value,
  )
})

/** Per-item count of currently-selected documents. */
const itemSelectedCount = computed<Record<string, number>>(() => {
  const map: Record<string, number> = {}
  if (!task.value) return map
  const sel = selectedSet.value
  for (const d of task.value.matched_documents || []) {
    if (sel.has(d.document_id)) {
      map[d.item_key] = (map[d.item_key] || 0) + 1
    }
  }
  return map
})

const canReparse = computed(
  () =>
    !!task.value &&
    !isTransient(task.value.status) &&
    task.value.status !== 'sent',
)
const canRematch = computed(
  () =>
    !!task.value &&
    !isTransient(task.value.status) &&
    (task.value.parsed_items?.length || 0) > 0 &&
    task.value.status !== 'sent',
)
const canPack = computed(
  () =>
    !!task.value &&
    !isTransient(task.value.status) &&
    (task.value.selected_documents?.length || 0) > 0 &&
    task.value.status !== 'pending_review' &&
    task.value.status !== 'sent',
)
const canSubmit = computed(
  () =>
    !!task.value &&
    !!task.value.zip_oss_key &&
    task.value.status !== 'pending_review' &&
    task.value.status !== 'sent',
)
const canDownload = computed(
  () => !!task.value && !!task.value.zip_oss_key,
)

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

const formatScore = (s: number): string => {
  if (typeof s !== 'number' || Number.isNaN(s)) return '-'
  return `${(s * 100).toFixed(0)}%`
}

const goBack = () => {
  router.push({ name: 'finance-materials' })
}

const rejectRules = computed<FormRules>(() => ({
  comment: [
    {
      required: true,
      message: t('views.finance.materials.validation.rejectReasonRequired'),
      trigger: 'blur',
    },
  ],
}))

const fetchTask = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !pk.value) return
  loading.value = true
  try {
    const t1 = await store.fetchDetail(wid, pk.value)
    if (t1) {
      // Default focused item to the first parsed item.
      if (!focusedItemKey.value && t1.parsed_items?.length) {
        focusedItemKey.value = t1.parsed_items[0].key
      }
      // Kick off polling if currently in a transient state.
      if (isTransient(t1.status)) {
        store.pollUntilStatusStable(wid, t1.id).catch(() => undefined)
      }
    }
  } finally {
    loading.value = false
  }
}

const onReparse = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  await store.triggerParse(wid, task.value.id)
  store.pollUntilStatusStable(wid, task.value.id).catch(() => undefined)
}

const onRematch = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  await store.triggerMatch(wid, task.value.id)
  store.pollUntilStatusStable(wid, task.value.id).catch(() => undefined)
}

const onSummarize = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  summarizing.value = true
  try {
    await store.triggerSummarize(wid, task.value.id)
    // The summary is regenerated asynchronously, but the trigger acknowledged.
    // If the latest summary still looks like the backend fallback stub, warn
    // the user so they don't think AI actually wrote it.
    const fresh = focusedDoc.value?.ai_summary || ''
    if (fresh.startsWith('[AI 待生成:')) {
      MsgWarning(t('views.finance.materials.detail.summarizeFallback'))
    } else {
      MsgSuccess(t('views.finance.materials.detail.summarizeSuccess'))
    }
  } finally {
    summarizing.value = false
  }
}

const onPack = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  await store.triggerPack(wid, task.value.id)
  MsgSuccess(t('views.finance.materials.detail.packSuccess'))
}

/**
 * Gate 7 Track B: retry whichever step failed. We can't infer the exact
 * failing step from `error_message` alone, so use the persisted state:
 *  - no parsed_items  → retry parse
 *  - parsed_items but no matched_documents → retry match
 *  - selected_documents but no zip_oss_key → retry pack
 *  - default → retry parse (safest restart)
 */
const onRetryLastStep = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  const t1 = task.value
  if (!t1.parsed_items || t1.parsed_items.length === 0) {
    await store.triggerParse(wid, t1.id)
  } else if (!t1.matched_documents || t1.matched_documents.length === 0) {
    await store.triggerMatch(wid, t1.id)
  } else if (
    t1.selected_documents &&
    t1.selected_documents.length > 0 &&
    !t1.zip_oss_key
  ) {
    await store.triggerPack(wid, t1.id)
  } else {
    await store.triggerParse(wid, t1.id)
  }
  store.pollUntilStatusStable(wid, t1.id).catch(() => undefined)
}

const onSubmit = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  await store.triggerSubmitReview(wid, task.value.id)
  MsgSuccess(t('views.finance.materials.detail.submitSuccess'))
}

const onApprove = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  try {
    await MsgConfirm(
      t('views.finance.materials.detail.approveConfirmTitle'),
      t('views.finance.materials.detail.approveConfirmDesc'),
    )
  } catch {
    return
  }
  await store.triggerReview(wid, task.value.id, { action: 'pass' })
  MsgSuccess(t('views.finance.materials.detail.approveSuccess'))
}

const openRejectDialog = () => {
  rejectForm.value.comment = ''
  rejectDialogVisible.value = true
  // Defer field clear until the form is mounted.
  setTimeout(() => rejectFormRef.value?.clearValidate(), 0)
}

const confirmReject = async () => {
  if (!rejectFormRef.value) return
  await rejectFormRef.value.validate(async (valid) => {
    if (!valid) return
    const wid = user.getWorkspaceId()
    if (!wid || !task.value) return
    await store.triggerReview(wid, task.value.id, {
      action: 'reject',
      comment: rejectForm.value.comment,
    })
    MsgSuccess(t('views.finance.materials.detail.rejectSuccess'))
    rejectDialogVisible.value = false
  })
}

const onDownload = async () => {
  const wid = user.getWorkspaceId()
  if (!wid || !task.value) return
  try {
    await downloadZip(
      wid,
      task.value.id,
      `${task.value.title || t('views.finance.materials.detail.downloadFallbackName')}.zip`,
    )
  } catch (err) {
    // exportFile already surfaces server errors; only surface unexpected ones.
    if (err instanceof Error && err.message) {
      MsgError(err.message)
    }
  }
}

const toggleSelect = async (doc: MatchedDocument, checked: boolean) => {
  if (!task.value || !canEdit.value) return
  if (isLocked(doc)) return
  const wid = user.getWorkspaceId()
  if (!wid) return
  const currentSet = new Set(task.value.selected_documents || [])
  if (checked) {
    currentSet.add(doc.document_id)
  } else {
    currentSet.delete(doc.document_id)
  }
  const next = Array.from(currentSet)
  await store.saveSelection(wid, task.value.id, {
    selected_documents: next,
  })
}

const openInKnowledge = (doc: MatchedDocument) => {
  // Knowledge document detail route — we use a permissive new-tab navigation
  // so a user without that page still lands on the knowledge index.
  const href = `/knowledge?documentId=${encodeURIComponent(doc.document_id)}`
  window.open(href, '_blank', 'noopener,noreferrer')
}

// Reset focused doc when item changes.
watch(focusedItemKey, () => {
  focusedDoc.value = null
})

// Reset focused doc when the focused doc is no longer in the matched list
// (e.g. after a rematch removed it).
watch(matchedForFocused, (list) => {
  if (
    focusedDoc.value &&
    !list.some((d) => d.document_id === focusedDoc.value!.document_id)
  ) {
    focusedDoc.value = null
  }
})

// Refetch on `pk` change as well as on first mount. Without the watcher,
// navigating between two materials-task detail pages without leaving the
// route reused the component instance and onMounted didn't fire again,
// leaving stale state — and a known race left the page blank on first SPA
// jump from the list. `immediate: true` runs the load once on mount and
// closes the race.
watch(
  () => pk.value,
  async (next, prev) => {
    if (!next) return
    // Skip the spurious initial fire when prev === next on mount (Vue runs
    // immediate watcher with prev === undefined → no skip needed).
    if (prev === next) return
    const wid = user.getWorkspaceId()
    if (wid && projectStore.list.length === 0) {
      projectStore.fetchList(wid).catch(() => undefined)
    }
    await fetchTask()
    fetchSendLogs().catch(() => undefined)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (task.value) {
    store.stopPolling(task.value.id)
  }
  store.selected = null
})
</script>

<style lang="scss" scoped>
.finance-materials-detail {
  background: var(--el-bg-color);
  min-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--el-border-color-lighter);
    background: var(--el-bg-color);
    padding: 16px 24px;
    flex-wrap: wrap;
    gap: 12px;
  }

  &__title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__project {
    color: var(--el-text-color-regular);
    font-size: 13px;
  }

  &__body {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  &__progress,
  &__empty,
  &__failed {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: var(--el-text-color-regular);
    padding: 48px 24px;
    gap: 12px;
  }

  &__spinner {
    font-size: 32px;
    color: var(--el-color-primary);
  }

  &__failed-card {
    max-width: 560px;
    text-align: left;
  }

  &__error-msg {
    color: var(--el-color-danger);
    margin: 0 0 12px;
    white-space: pre-wrap;
    word-break: break-word;
  }

  &__panes {
    flex: 1;
    display: grid;
    grid-template-columns: 25% 45% 30%;
    min-height: 0;
    border-top: 1px solid var(--el-border-color-lighter);
  }

  &__pane {
    border-right: 1px solid var(--el-border-color-lighter);
    display: flex;
    flex-direction: column;
    min-height: 0;

    &--p3 {
      border-right: none;
    }
  }

  &__pane-header {
    padding: 12px 16px;
    font-weight: 600;
    border-bottom: 1px solid var(--el-border-color-lighter);
    background: var(--el-fill-color-light);
    font-size: 14px;
    color: var(--el-text-color-primary);
  }

  &__pane-empty {
    padding: 32px 16px;
    color: var(--el-text-color-placeholder);
    text-align: center;
  }

  &__items {
    list-style: none;
    margin: 0;
    padding: 8px 0;
    overflow-y: auto;
  }

  &__item {
    padding: 10px 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    border-left: 3px solid transparent;
    transition: background 0.15s ease;
    color: var(--el-text-color-regular);

    &:hover {
      background: var(--el-fill-color);
    }

    &--active {
      background: var(--el-color-primary-light-9);
      border-left-color: var(--el-color-primary);
      color: var(--el-text-color-primary);
      font-weight: 500;
    }
  }

  &__item-label {
    flex: 1;
    word-break: break-word;
  }

  &__required {
    color: var(--el-color-danger);
    margin-left: 4px;
  }

  &__item-badge {
    background: var(--el-color-primary);
    color: #fff;
    border-radius: 10px;
    padding: 0 8px;
    font-size: 12px;
    line-height: 18px;
    min-width: 24px;
    text-align: center;
  }

  &__matched {
    flex: 1;
    overflow-y: auto;
    padding: 8px 16px;
  }

  &__matched-empty {
    padding: 24px 0;
    text-align: center;
    color: var(--el-text-color-placeholder);
  }

  &__doc-row {
    display: flex;
    gap: 12px;
    padding: 12px;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 6px;
    margin-bottom: 8px;
    cursor: pointer;
    background: var(--el-bg-color);

    &:hover {
      border-color: var(--el-color-primary-light-5);
    }

    &--active {
      border-color: var(--el-color-primary);
      background: var(--el-color-primary-light-9);
    }

    &--locked {
      opacity: 0.65;
    }
  }

  &__doc-info {
    flex: 1;
    min-width: 0;
  }

  &__doc-name {
    font-weight: 500;
    color: var(--el-text-color-primary);
    word-break: break-word;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  &__doc-meta {
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--el-text-color-regular);
  }

  &__score {
    color: var(--el-text-color-regular);
  }

  &__snippet {
    margin-top: 6px;
    font-size: 12px;
    color: var(--el-text-color-regular);
    background: var(--el-fill-color-lighter);
    border-radius: 4px;
    padding: 6px 8px;
    line-height: 1.5;
    word-break: break-word;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__lock {
    color: var(--el-color-warning);
    font-size: 12px;
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }

  &__add-doc {
    padding: 12px 0;
    text-align: center;
  }

  &__doc-detail {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
    flex: 1;
  }

  &__doc-detail-name {
    font-weight: 600;
    color: var(--el-text-color-primary);
    word-break: break-word;
  }

  &__doc-detail-meta {
    display: flex;
    gap: 8px;
  }

  &__summary {
    flex: 1;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.6;
    color: var(--el-text-color-regular);
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
    padding: 12px;
    min-height: 120px;
  }

  &__doc-detail-actions {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  &__progress-msg {
    color: var(--el-text-color-regular);
    font-size: 14px;
  }

  &__picker-hint {
    color: var(--el-text-color-placeholder);
    text-align: center;
    padding: 24px 0;
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>

<template>
  <el-drawer
    v-model="innerVisible"
    :title="$t('views.finance.progressPage.drawerTitle')"
    direction="rtl"
    size="600px"
    @open="onOpen"
  >
    <div v-if="localProject" v-loading="loading" class="psd">
      <!-- 项目概要 -->
      <div class="psd__head">
        <div class="psd__name">{{ localProject.name }}</div>
        <div class="psd__tags">
          <el-tag size="small" disable-transitions>
            {{ $t('views.finance.project.projectType.' + localProject.project_type) }}
          </el-tag>
          <el-tag
            size="small"
            :type="statusTagType(localProject.status)"
            disable-transitions
          >
            {{ $t('views.finance.project.statusOptions.' + localProject.status) }}
          </el-tag>
        </div>
        <div class="psd__meta">
          <span>{{ $t('views.finance.progressPage.owner') }}：{{ ownerName(localProject.owner_id) }}</span>
          <span v-if="localProject.counterparty">
            {{ $t('views.finance.progressPage.counterparty') }}：{{ localProject.counterparty }}
          </span>
        </div>
      </div>

      <!-- 流转操作 -->
      <div v-if="canEdit" class="psd__actions">
        <el-button type="primary" :disabled="!canAdvance" @click="doAdvance">
          {{ $t('views.finance.progressPage.advance') }}
        </el-button>
        <el-button :disabled="!canRollback" @click="doRollback">
          {{ $t('views.finance.progressPage.rollback') }}
        </el-button>
        <span v-if="localProject.status === 'terminated'" class="psd__hint">
          {{ $t('views.finance.progressPage.terminatedHint') }}
        </span>
      </div>

      <!-- 阶段清单 -->
      <div class="psd__stages">
        <div
          v-for="s in stages"
          :key="s.id"
          class="psd__stage"
          :class="{ 'is-active': s.status === 'active' }"
        >
          <div class="psd__stage-top">
            <span class="psd__stage-name">
              {{ s.stage_order + 1 }}. {{ s.stage_label || s.stage_key }}
            </span>
            <el-tag size="small" :type="stageTagType(s.status)" disable-transitions>
              {{ $t('views.finance.progressPage.stageStatus.' + s.status) }}
            </el-tag>
          </div>
          <div class="psd__stage-meta">
            <span>{{ $t('views.finance.progressPage.stageHeader.planned') }}：{{ fmtDate(s.planned_at) }}</span>
            <span>{{ $t('views.finance.progressPage.stageHeader.actual') }}：{{ fmtDate(s.actual_at) }}</span>
            <span>{{ $t('views.finance.progressPage.stageOwner') }}：{{ ownerName(s.owner_id) }}</span>
          </div>
          <div v-if="s.note" class="psd__stage-note">{{ s.note }}</div>
          <div v-if="canEdit" class="psd__stage-edit">
            <el-button link type="primary" size="small" @click="openEdit(s)">
              {{ $t('views.finance.progressPage.editStage') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 单阶段编辑 -->
    <el-dialog
      v-model="editVisible"
      :title="$t('views.finance.progressPage.editStage')"
      width="420"
      append-to-body
    >
      <el-form label-position="top">
        <el-form-item :label="$t('views.finance.progressPage.plannedAt')">
          <el-date-picker
            v-model="editForm.planned_at"
            type="date"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="$t('views.finance.progressPage.stageOwner')">
          <el-select
            v-model="editForm.owner_id"
            clearable
            filterable
            :placeholder="$t('views.finance.progressPage.inheritOwner')"
            style="width: 100%"
          >
            <el-option
              v-for="u in ownerOptions"
              :key="u.value"
              :label="u.label"
              :value="u.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('views.finance.progressPage.note')">
          <el-input
            v-model="editForm.note"
            type="textarea"
            :rows="2"
            maxlength="1000"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveStage">
          {{ $t('common.save') }}
        </el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import type {
  GanttProject,
  ProjectStatus,
  StageRecord,
  StageStatus,
} from '@/api/finance/type'
import {
  advanceStage,
  getProjectStages,
  rollbackStage,
  updateStage,
} from '@/api/finance/progress'

interface OwnerOption {
  label: string
  value: string
}
type TagType = 'success' | 'info' | 'warning' | 'danger' | 'primary'

const props = defineProps<{
  visible: boolean
  workspaceId: string
  project: GanttProject | null
  canEdit: boolean
  ownerNameMap: Record<string, string>
  ownerOptions: OwnerOption[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'changed'): void
}>()

const innerVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const loading = ref(false)
const saving = ref(false)
const localProject = ref<GanttProject | null>(null)
const stages = ref<StageRecord[]>([])

const activeStage = computed(
  () => stages.value.find((s) => s.status === 'active') || null,
)
const canAdvance = computed(
  () =>
    props.canEdit &&
    !!localProject.value &&
    localProject.value.status !== 'terminated' &&
    !!activeStage.value &&
    activeStage.value.stage_order < stages.value.length - 1,
)
const canRollback = computed(
  () =>
    props.canEdit &&
    !!localProject.value &&
    localProject.value.status !== 'terminated' &&
    !!activeStage.value &&
    activeStage.value.stage_order > 0,
)

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

function statusTagType(s: ProjectStatus): TagType {
  const map: Record<ProjectStatus, TagType> = {
    preparing: 'info',
    materials: 'primary',
    engaging: 'warning',
    landed: 'success',
    terminated: 'danger',
  }
  return map[s] || 'info'
}

function stageTagType(s: StageStatus): TagType {
  const map: Record<StageStatus, TagType> = {
    pending: 'info',
    active: 'primary',
    done: 'success',
    skipped: 'info',
  }
  return map[s] || 'info'
}

async function refreshStages() {
  if (!localProject.value) return
  loading.value = true
  try {
    const res = await getProjectStages(props.workspaceId, localProject.value.id)
    stages.value = res?.data || []
  } finally {
    loading.value = false
  }
}

async function onOpen() {
  localProject.value = props.project ? { ...props.project } : null
  stages.value = props.project ? [...props.project.stages] : []
  await refreshStages()
}

async function doAdvance() {
  const proj = localProject.value
  if (!proj) return
  try {
    await ElMessageBox.confirm(
      t('views.finance.progressPage.advanceConfirm', { name: proj.name }),
      t('common.tip'),
    )
  } catch {
    return
  }
  const res = await advanceStage(props.workspaceId, proj.id)
  if (res?.data) {
    localProject.value = { ...proj, ...res.data }
    await refreshStages()
    MsgSuccess(t('views.finance.progressPage.advanceSuccess'))
    emit('changed')
  }
}

async function doRollback() {
  const proj = localProject.value
  if (!proj) return
  let note = ''
  try {
    const r = await ElMessageBox.prompt(
      t('views.finance.progressPage.rollbackPrompt'),
      t('views.finance.progressPage.rollbackPromptTitle'),
      { inputType: 'textarea' },
    )
    note = (r.value || '').trim()
  } catch {
    return
  }
  const res = await rollbackStage(props.workspaceId, proj.id, note)
  if (res?.data) {
    localProject.value = { ...proj, ...res.data }
    await refreshStages()
    MsgSuccess(t('views.finance.progressPage.rollbackSuccess'))
    emit('changed')
  }
}

const editVisible = ref(false)
const editingKey = ref('')
const editForm = reactive<{
  planned_at: string | null
  owner_id: string | null
  note: string
}>({
  planned_at: null,
  owner_id: null,
  note: '',
})

function openEdit(s: StageRecord) {
  editingKey.value = s.stage_key
  editForm.planned_at = s.planned_at
  editForm.owner_id = s.owner_id
  editForm.note = s.note || ''
  editVisible.value = true
}

async function saveStage() {
  if (!localProject.value || !editingKey.value) return
  saving.value = true
  try {
    const res = await updateStage(
      props.workspaceId,
      localProject.value.id,
      editingKey.value,
      {
        planned_at: editForm.planned_at,
        owner_id: editForm.owner_id || null,
        note: editForm.note,
      },
    )
    if (res?.data) {
      editVisible.value = false
      await refreshStages()
      MsgSuccess(t('views.finance.progressPage.stageSaved'))
      emit('changed')
    }
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.psd {
  &__head {
    padding-bottom: 12px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  &__name {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__tags {
    margin-top: 8px;
    display: flex;
    gap: 8px;
  }

  &__meta {
    margin-top: 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }

  &__actions {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 0;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  &__hint {
    font-size: 12px;
    color: var(--el-color-danger);
  }

  &__stages {
    margin-top: 8px;
  }

  &__stage {
    padding: 12px;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 6px;
    margin-bottom: 8px;

    &.is-active {
      border-color: var(--el-color-primary);
      background: var(--el-color-primary-light-9);
    }
  }

  &__stage-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__stage-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--el-text-color-primary);
  }

  &__stage-meta {
    margin-top: 6px;
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__stage-note {
    margin-top: 6px;
    font-size: 12px;
    color: var(--el-text-color-regular);
    white-space: pre-wrap;
  }

  &__stage-edit {
    margin-top: 4px;
    text-align: right;
  }
}
</style>

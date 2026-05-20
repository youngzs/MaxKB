<template>
  <div class="finance-template-detail p-24" v-loading="loading">
    <div class="finance-template-detail__header flex-between mb-16">
      <div class="flex" style="align-items: center; gap: 12px">
        <el-button link @click="goBack">
          {{ $t('views.finance.templateLib.backToList') }}
        </el-button>
        <h2 v-if="template" class="finance-template-detail__title">
          <span v-if="!editingName" @click="canEdit && (editingName = true)">
            {{ template.name }}
            <el-button
              v-if="canEdit"
              link
              type="primary"
              size="small"
              @click.stop="editingName = true"
            >
              <AppIcon iconName="app-edit-outlined" />
            </el-button>
          </span>
          <el-input
            v-else
            v-model="form.name"
            size="small"
            style="width: 320px"
            maxlength="200"
            @keyup.enter="editingName = false"
            @blur="editingName = false"
          />
        </h2>
      </div>
      <div class="flex" style="gap: 8px; align-items: center">
        <el-button
          v-if="template"
          link
          type="primary"
          :loading="downloadLoading"
          @click="onDownload"
        >
          <AppIcon iconName="app-download" class="mr-4" />
          {{ $t('views.finance.templateLib.detailDownload') }}
        </el-button>
        <el-tag
          v-if="template"
          :type="scenarioTagType(template.scenario)"
          disable-transitions
        >
          {{ $t(`views.finance.templateLib.scenario.${template.scenario}`) }}
        </el-tag>
        <el-tag v-if="template" type="info" disable-transitions>
          v{{ template.version }}
        </el-tag>
      </div>
    </div>

    <el-card v-if="template" shadow="never" class="mb-16">
      <template #header>
        <div class="finance-template-detail__card-header">
          <strong>{{ $t('views.finance.templateLib.placeholderEditor.title') }}</strong>
          <el-button
            v-if="canEdit && form.placeholders.length > 0"
            type="primary"
            plain
            size="small"
            :loading="suggesting"
            @click="handleSuggestPlaceholders"
          >
            <AppIcon iconName="app-magic-stick" class="mr-4" />
            {{ $t('views.finance.templateLib.placeholderEditor.suggest') }}
          </el-button>
        </div>
      </template>

      <el-row :gutter="16" class="mb-16">
        <el-col :span="8">
          <div class="finance-template-detail__field">
            <label>{{ $t('views.finance.templateLib.fields.scenario') }}</label>
            <el-select v-model="form.scenario" style="width: 100%" :disabled="!canEdit">
              <el-option
                v-for="opt in scenarioOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="finance-template-detail__field">
            <label>{{ $t('views.finance.templateLib.fields.isActive') }}</label>
            <el-switch v-model="form.is_active" :disabled="!canEdit" />
          </div>
        </el-col>
        <el-col :span="8">
          <div class="finance-template-detail__field">
            <label>{{ $t('views.finance.templateLib.fields.updatedAt') }}</label>
            <div>{{ formatDate(template.updated_at) }}</div>
          </div>
        </el-col>
      </el-row>

      <el-table
        v-if="form.placeholders.length > 0"
        :data="form.placeholders"
        stripe
        style="width: 100%"
      >
        <el-table-column
          prop="key"
          :label="$t('views.finance.templateLib.placeholderEditor.key')"
          min-width="160"
        >
          <template #default="{ row }">
            <code class="finance-template-detail__key">{{ row.key }}</code>
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('views.finance.templateLib.placeholderEditor.label')"
          min-width="180"
        >
          <template #default="{ row }">
            <el-input v-model="row.label" :disabled="!canEdit" />
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('views.finance.templateLib.placeholderEditor.type')"
          width="140"
        >
          <template #default="{ row }">
            <el-select v-model="row.type" :disabled="!canEdit" style="width: 100%">
              <el-option
                v-for="opt in placeholderTypeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('views.finance.templateLib.placeholderEditor.required')"
          width="80"
          align="center"
        >
          <template #default="{ row }">
            <el-switch v-model="row.required" :disabled="!canEdit" />
          </template>
        </el-table-column>
        <el-table-column min-width="280">
          <template #header>
            <span style="display: inline-flex; align-items: center; gap: 4px">
              {{ $t('views.finance.templateLib.placeholderEditor.aiHintColumn') }}
              <el-tooltip placement="top">
                <template #content>
                  <div style="max-width: 320px; line-height: 1.6">
                    <strong>{{ $t('views.finance.templateLib.placeholderEditor.aiHintTooltip.intro') }}</strong>
                    <br />
                    {{ $t('views.finance.templateLib.placeholderEditor.aiHintTooltip.whatLabel') }}{{ $t('views.finance.templateLib.placeholderEditor.aiHintTooltip.what') }}
                    <br /><br />
                    {{ $t('views.finance.templateLib.placeholderEditor.aiHintTooltip.whatNotLabel') }}<strong>{{ $t('views.finance.templateLib.placeholderEditor.aiHintTooltip.whatNot') }}</strong>
                  </div>
                </template>
                <el-icon style="font-size: 14px; color: var(--el-color-info); cursor: help">
                  <QuestionFilled />
                </el-icon>
              </el-tooltip>
            </span>
          </template>
          <template #default="{ row }">
            <el-input
              v-model="row.ai_hint"
              type="textarea"
              :rows="2"
              :disabled="!canEdit"
              :placeholder="$t('views.finance.templateLib.placeholderEditor.aiHintPlaceholder')"
            />
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('views.finance.templateLib.placeholderEditor.enumOptionsHelp')"
          min-width="200"
        >
          <template #default="{ row, $index }">
            <el-input
              v-if="row.type === 'enum'"
              :model-value="row.enum_options.join(',')"
              :disabled="!canEdit"
              :placeholder="$t('views.finance.templateLib.placeholderEditor.enumOptionsPlaceholder')"
              @update:model-value="(v: string) => updateEnumOptions($index, v)"
            />
            <span v-else class="finance-template-detail__muted">—</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="finance-template-detail__placeholder">
        {{ $t('views.finance.templateLib.placeholderEditor.empty') }}
      </div>

      <!-- sticky 底栏：表格 13+ 行时整页可滚动，但保存按钮始终钉在视口底部 -->
      <div v-if="canEdit" class="finance-template-detail__actions">
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ $t('views.finance.templateLib.placeholderEditor.save') }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MsgError, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import type {
  Placeholder,
  PlaceholderType,
  Template,
  TemplateScenario,
  TemplateUpdate,
} from '@/api/finance/type'
import { downloadTemplate } from '@/api/finance/template'
import { QuestionFilled } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { user, financeTemplate: store } = useStore()

const loading = ref(false)
const saving = ref(false)
const downloadLoading = ref(false)
const suggesting = ref(false)
const template = ref<Template | null>(null)
const editingName = ref(false)

async function onDownload() {
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId || !template.value) return
  downloadLoading.value = true
  try {
    // 文件名 fallback —— Content-Disposition 缺失时退化用模板名；
    // 后端 RFC 5987 头通常会覆盖这个值。
    const safeName = (template.value.name || 'template').replace(/[\\/:*?"<>|]/g, '_')
    await downloadTemplate(workspaceId, template.value.id, `${safeName}.docx`)
  } finally {
    downloadLoading.value = false
  }
}

interface EditableForm {
  name: string
  scenario: TemplateScenario
  is_active: boolean
  placeholders: Placeholder[]
}

const form = reactive<EditableForm>({
  name: '',
  scenario: 'internal_report',
  is_active: true,
  placeholders: [],
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

const scenarioOptions: { value: TemplateScenario; label: string }[] = [
  { value: 'internal_report', label: t('views.finance.templateLib.scenario.internal_report') },
  { value: 'meeting', label: t('views.finance.templateLib.scenario.meeting') },
  { value: 'system_process', label: t('views.finance.templateLib.scenario.system_process') },
  { value: 'other', label: t('views.finance.templateLib.scenario.other') },
]

const placeholderTypeOptions: { value: PlaceholderType; label: string }[] = [
  { value: 'text', label: t('views.finance.templateLib.placeholderType.text') },
  { value: 'long_text', label: t('views.finance.templateLib.placeholderType.long_text') },
  { value: 'number', label: t('views.finance.templateLib.placeholderType.number') },
  { value: 'date', label: t('views.finance.templateLib.placeholderType.date') },
  { value: 'enum', label: t('views.finance.templateLib.placeholderType.enum') },
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

const updateEnumOptions = (index: number, raw: string) => {
  const opts = raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
  form.placeholders[index].enum_options = opts
}

const hydrate = (tpl: Template) => {
  form.name = tpl.name
  form.scenario = tpl.scenario
  form.is_active = tpl.is_active
  // Deep-copy placeholders so editing rows doesn't mutate the store object.
  form.placeholders = (tpl.placeholders || []).map((p) => ({
    key: p.key,
    label: p.label,
    type: p.type,
    required: p.required ?? false,
    ai_hint: p.ai_hint,
    enum_options: [...(p.enum_options || [])],
  }))
}

const fetchDetail = async () => {
  const workspaceId = user.getWorkspaceId()
  const pk = route.params.pk as string
  if (!workspaceId || !pk) return
  loading.value = true
  try {
    const data = await store.fetchDetail(workspaceId, pk)
    template.value = data
    if (data) hydrate(data)
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push({ name: 'finance-template' })
}

const handleSave = async () => {
  if (!template.value) return
  // Validate each placeholder has a non-empty label.
  for (const p of form.placeholders) {
    if (!p.label || !p.label.trim()) {
      MsgError(t('views.finance.templateLib.validation.labelRequired'))
      return
    }
  }
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  const payload: TemplateUpdate = {
    name: form.name.trim(),
    scenario: form.scenario,
    is_active: form.is_active,
    placeholders: form.placeholders.map((p) => ({
      key: p.key,
      label: p.label.trim(),
      type: p.type,
      required: p.required,
      ai_hint: p.ai_hint || '',
      enum_options: p.type === 'enum' ? p.enum_options : [],
    })),
  }
  saving.value = true
  try {
    const updated = await store.updateMeta(workspaceId, template.value.id, payload)
    if (updated) {
      template.value = updated
      hydrate(updated)
      MsgSuccess(t('views.finance.templateLib.saveSuccess'))
    }
  } finally {
    saving.value = false
  }
}

const handleSuggestPlaceholders = async () => {
  if (!template.value) return
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  suggesting.value = true
  try {
    const suggestions = await store.suggestPlaceholders(workspaceId, template.value.id)
    const byKey = new Map(suggestions.map((item) => [item.key, item]))
    form.placeholders = form.placeholders.map((item) => {
      const suggested = byKey.get(item.key)
      if (!suggested) return { ...item, required: item.required ?? false }
      return {
        ...item,
        label: suggested.label || item.label,
        type: suggested.type || item.type,
        required: suggested.required ?? false,
        ai_hint: suggested.ai_hint || item.ai_hint,
        enum_options: suggested.enum_options?.length ? suggested.enum_options : item.enum_options,
      }
    })
    MsgSuccess(t('views.finance.templateLib.placeholderEditor.suggestSuccess'))
  } finally {
    suggesting.value = false
  }
}

watch(
  () => route.params.pk,
  () => {
    if (route.name === 'finance-template-detail') fetchDetail()
  },
)

onMounted(() => {
  fetchDetail()
})
</script>

<style lang="scss" scoped>
.finance-template-detail {
  height: 100%;
  overflow-y: auto;
  min-height: calc(100vh - 80px);
  background: var(--el-bg-color);
  box-sizing: border-box;

  &__title {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }

  &__field {
    label {
      display: block;
      font-size: 13px;
      color: var(--el-text-color-regular);
      margin-bottom: 4px;
    }
  }

  &__card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  &__key {
    background: var(--el-fill-color-light);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
  }

  &__muted {
    color: var(--el-text-color-secondary);
  }

  &__placeholder {
    text-align: center;
    color: var(--el-text-color-secondary);
    padding: 32px 0;
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
    // sticky 到视口底部 —— 长表格不会把保存按钮顶出可视范围。
    // background + border-top 防止下方内容透出来。
    position: sticky;
    bottom: 0;
    background: var(--el-bg-color);
    padding: 12px 0;
    margin-top: 16px;
    border-top: 1px solid var(--el-border-color-lighter);
    z-index: 1;
  }
}
</style>

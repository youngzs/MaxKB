<template>
  <div class="finance-wizard p-24">
    <div class="finance-wizard__header flex-between mb-16">
      <div class="flex" style="align-items: center; gap: 12px">
        <el-button link @click="goBack">
          {{ $t('views.finance.documentsLib.wizard.backToList') }}
        </el-button>
        <h2 class="finance-wizard__title">
          {{ $t('views.finance.documentsLib.wizard.title') }}
        </h2>
      </div>
    </div>

    <el-card shadow="never" class="mb-16">
      <el-steps :active="active" finish-status="success" simple>
        <el-step :title="$t('views.finance.documentsLib.wizard.steps.selectTemplate')" />
        <el-step :title="$t('views.finance.documentsLib.wizard.steps.selectProject')" />
        <el-step :title="$t('views.finance.documentsLib.wizard.steps.fillPlaceholders')" />
        <el-step :title="$t('views.finance.documentsLib.wizard.steps.previewGenerate')" />
      </el-steps>
    </el-card>

    <!-- Step 1: select template -->
    <el-card v-show="active === 0" shadow="never" class="mb-16">
      <div class="finance-wizard__filter-bar mb-16">
        <!--
          Element Plus 3.0 — `label` 作为 value 已废弃；改用显式 `value`。
          这里 slot 内容就是显示文本，所以保留 slot 即可。
        -->
        <el-radio-group v-model="templateScenarioFilter" @change="onTemplateScenarioChange">
          <el-radio-button value="">
            {{ $t('views.finance.templateLib.scenario.all') }}
          </el-radio-button>
          <el-radio-button
            v-for="opt in scenarioOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <div v-loading="templateStore.loading" class="finance-wizard__grid">
        <el-card
          v-for="tpl in activeTemplates"
          :key="tpl.id"
          shadow="hover"
          :class="[
            'finance-wizard__select-card',
            { 'is-selected': selectedTemplateId === tpl.id },
          ]"
          @click="selectedTemplateId = tpl.id"
        >
          <el-tag size="small" :type="scenarioTagType(tpl.scenario)" disable-transitions>
            {{ $t(`views.finance.templateLib.scenario.${tpl.scenario}`) }}
          </el-tag>
          <h3 class="finance-wizard__select-card-name">{{ tpl.name }}</h3>
          <div class="finance-wizard__select-card-meta">
            {{ $t('views.finance.templateLib.fields.placeholderCount') }}:
            {{ tpl.placeholders?.length || 0 }} ·
            v{{ tpl.version }}
          </div>
        </el-card>
      </div>

      <!-- Step-1 empty state: no templates uploaded yet. Surface a hard
           dead-end here (the wizard literally can't continue without a
           template) plus a one-click jump to the template library so the
           user doesn't have to hunt for it in the side menu. -->
      <el-empty
        v-if="!templateStore.loading && activeTemplates.length === 0"
        :image-size="100"
        class="finance-wizard__empty"
      >
        <template #description>
          <div class="finance-empty-state">
            <h3>{{ $t('views.finance.documentsLib.wizard.noTemplateTitle') }}</h3>
            <p class="text-secondary">
              {{ $t('views.finance.documentsLib.wizard.noTemplate') }}
            </p>
            <el-button type="primary" @click="goToTemplateLibrary">
              {{ $t('views.finance.documentsLib.wizard.noTemplateCta') }}
            </el-button>
          </div>
        </template>
      </el-empty>
    </el-card>

    <!-- Step 2: select project -->
    <el-card v-show="active === 1" shadow="never" class="mb-16">
      <div class="finance-wizard__filter-bar mb-16 flex">
        <el-input
          v-model="projectKeyword"
          :placeholder="$t('views.finance.project.searchPlaceholder')"
          clearable
          style="width: 240px"
          @input="onProjectKeywordInput"
          @clear="onProjectKeywordInput('')"
        />
        <el-select
          v-model="projectStatusFilter"
          :placeholder="$t('views.finance.project.statusFilterAll')"
          clearable
          style="width: 160px; margin-left: 12px"
          @change="onProjectStatusChange"
        >
          <el-option
            v-for="opt in projectStatusOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>

      <el-table
        v-loading="projectStore.loading"
        :data="projectStore.list"
        stripe
        style="width: 100%"
        highlight-current-row
        @row-click="(row: Project) => (selectedProjectId = row.id)"
      >
        <el-table-column width="56">
          <template #default="{ row }">
            <el-radio
              :model-value="selectedProjectId"
              :value="row.id"
              @click.stop="selectedProjectId = row.id"
            >
              <template #default>&nbsp;</template>
            </el-radio>
          </template>
        </el-table-column>
        <el-table-column
          prop="name"
          :label="$t('views.finance.project.columns.name')"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column
          prop="code"
          :label="$t('views.finance.project.columns.code')"
          min-width="120"
          show-overflow-tooltip
        />
        <el-table-column
          :label="$t('views.finance.project.columns.status')"
          width="120"
        >
          <template #default="{ row }">
            <el-tag :type="projectStatusTagType(row.status)" disable-transitions>
              {{ $t(`views.finance.project.statusOptions.${row.status}`) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!projectStore.loading && projectStore.list.length === 0" class="finance-wizard__empty">
        {{ $t('views.finance.documentsLib.wizard.noProject') }}
      </div>
    </el-card>

    <!-- Step 3: fill placeholders -->
    <el-card v-show="active === 2" shadow="never" class="mb-16">
      <div v-if="longTextPlaceholders.length > 0" class="mb-16 flex-between" style="align-items: center">
        <span class="finance-wizard__muted">
          {{ longTextPlaceholders.length }}
          ×
          {{ $t('views.finance.templateLib.placeholderType.long_text') }}
        </span>
        <el-button
          :loading="aiFillingAll"
          :disabled="aiFillingAll"
          type="primary"
          plain
          @click="aiFillAll"
        >
          <template v-if="aiFillingAll">
            {{ $t('views.finance.documentsLib.wizard.aiFillAllBusy', { n: longTextPlaceholders.length }) }}
          </template>
          <template v-else>
            <AppIcon iconName="app-magic-stick" class="mr-4" />
            {{ $t('views.finance.documentsLib.wizard.aiFillAll') }}
          </template>
        </el-button>
      </div>

      <!--
        Grid 布局：short 字段（text/number/date/enum）2 列摆放，long_text
        独占整行（textarea 需要横向空间放下多行内容）。响应式回落：
          xs/sm 1 列，md+ 起 long_text 始终 24，其他 span 12。
        旧版用单列堆叠 13+ 字段时滚动很长，且每个输入只用了不到一半的宽度。
      -->
      <el-form
        v-if="selectedTemplate && selectedTemplate.placeholders.length > 0"
        label-position="top"
        require-asterisk-position="right"
      >
        <el-row :gutter="20">
          <el-col
            v-for="ph in selectedTemplate.placeholders"
            :key="ph.key"
            :xs="24"
            :sm="ph.type === 'long_text' ? 24 : 12"
            :md="ph.type === 'long_text' ? 24 : 12"
          >
            <el-form-item :required="ph.required">
              <template #label>
                <span>{{ displayLabel(ph) }}</span>
                <code class="finance-wizard__key" :title="ph.key">{{ formatKey(ph.key) }}</code>
              </template>

              <template v-if="ph.type === 'text'">
                <el-input v-model="placeholderValues[ph.key] as string" maxlength="500" />
              </template>

              <template v-else-if="ph.type === 'long_text'">
                <div
                  class="finance-wizard__long-text"
                  :class="{ 'finance-wizard__long-text--flash': flashKeys[ph.key] }"
                >
                  <el-input
                    v-model="placeholderValues[ph.key] as string"
                    type="textarea"
                    :rows="4"
                    :disabled="loadingByKey[ph.key]"
                  />
                  <el-button
                    :loading="loadingByKey[ph.key]"
                    size="small"
                    plain
                    type="primary"
                    class="finance-wizard__ai-btn"
                    @click="aiFillOne(ph.key)"
                  >
                    <template v-if="loadingByKey[ph.key]">
                      {{ $t('views.finance.documentsLib.wizard.aiFillBusy') }}
                    </template>
                    <template v-else>
                      <AppIcon iconName="app-magic-stick" class="mr-4" />
                      {{ $t('views.finance.documentsLib.wizard.aiFillOne') }}
                    </template>
                  </el-button>
                </div>
              </template>

              <template v-else-if="ph.type === 'number'">
                <el-input-number
                  v-model="numericValues[ph.key]"
                  style="width: 100%"
                  :precision="2"
                  :step="1"
                  @change="(v: number | undefined) => (placeholderValues[ph.key] = v ?? '')"
                />
              </template>

              <template v-else-if="ph.type === 'date'">
                <el-date-picker
                  v-model="placeholderValues[ph.key] as string"
                  type="date"
                  value-format="YYYY-MM-DD"
                  style="width: 100%"
                />
              </template>

              <template v-else-if="ph.type === 'enum'">
                <el-select v-model="placeholderValues[ph.key] as string" style="width: 100%">
                  <el-option
                    v-for="opt in ph.enum_options"
                    :key="opt"
                    :label="opt"
                    :value="opt"
                  />
                </el-select>
              </template>

              <div v-if="ph.ai_hint" class="finance-wizard__hint">{{ ph.ai_hint }}</div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div v-else class="finance-wizard__empty">
        {{ $t('views.finance.templateLib.placeholderEditor.empty') }}
      </div>
    </el-card>

    <!-- Step 4: preview & generate -->
    <el-card v-show="active === 3" shadow="never" class="mb-16">
      <h3 class="finance-wizard__summary-title">
        {{ $t('views.finance.documentsLib.wizard.summary') }}
      </h3>
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="$t('views.finance.documentsLib.wizard.summaryTemplate')">
          {{ selectedTemplate?.name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('views.finance.documentsLib.wizard.summaryProject')">
          {{ selectedProject?.name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('views.finance.documentsLib.wizard.summaryValues')">
          <div class="finance-wizard__values">
            <div
              v-for="ph in selectedTemplate?.placeholders || []"
              :key="ph.key"
              class="finance-wizard__values-row"
            >
              <strong>{{ displayLabel(ph) }}:</strong>
              <span class="finance-wizard__values-text">
                {{ truncate(stringifyValue(placeholderValues[ph.key]), 120) }}
              </span>
            </div>
          </div>
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="errorMessage" class="finance-wizard__error">
        {{ errorMessage }}
      </div>
    </el-card>

    <!-- Footer -->
    <div class="finance-wizard__footer">
      <el-button v-if="active > 0" :disabled="generating" @click="prevStep">
        {{ $t('views.finance.documentsLib.wizard.prev') }}
      </el-button>
      <el-button
        v-if="active < 3"
        type="primary"
        :disabled="!canAdvance"
        @click="nextStep"
      >
        {{ $t('views.finance.documentsLib.wizard.next') }}
      </el-button>
      <el-button
        v-else
        type="primary"
        :loading="generating"
        @click="handleGenerate"
      >
        {{ $t('views.finance.documentsLib.wizard.generate') }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { debounce } from 'lodash'
import { MsgError, MsgSuccess, MsgWarning } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import type {
  Placeholder,
  Project,
  ProjectStatus,
  Template,
  TemplateScenario,
} from '@/api/finance/type'

const router = useRouter()
const {
  user,
  financeTemplate: templateStore,
  financeProject: projectStore,
  financeGeneration: generationStore,
} = useStore()

const active = ref(0)
const generating = ref(false)
const errorMessage = ref('')

const selectedTemplateId = ref<string>('')
const selectedProjectId = ref<string>('')

const templateScenarioFilter = ref<'' | TemplateScenario>('')
const projectKeyword = ref<string>('')
const projectStatusFilter = ref<'' | ProjectStatus>('')

const placeholderValues = reactive<Record<string, string | number>>({})
const numericValues = reactive<Record<string, number | undefined>>({})

/** Per-field in-flight state. A field is "busy" while its AI fill request
 *  is pending; the textarea is disabled and the trigger button shows
 *  a spinner with localized "Generating…" text. */
const loadingByKey = reactive<Record<string, boolean>>({})
/** Per-field flash state used to briefly highlight the textarea border
 *  after a successful fill. Cleared on a timer. */
const flashKeys = reactive<Record<string, boolean>>({})
const aiFillingAll = ref(false)

/** Backend fallback marker — when the LLM call fails the server still returns
 *  a stub like "[AI 待生成: <label>]" instead of a useful value, so we can
 *  count those separately and warn the user that AI didn't really fill it. */
const AI_FALLBACK_PREFIX = '[AI 待生成:'
const isAiFallback = (val: unknown): boolean =>
  typeof val === 'string' && val.startsWith(AI_FALLBACK_PREFIX)

const flashKey = (key: string) => {
  flashKeys[key] = true
  setTimeout(() => {
    flashKeys[key] = false
  }, 1500)
}

const scenarioOptions: { value: TemplateScenario; label: string }[] = [
  { value: 'internal_report', label: t('views.finance.templateLib.scenario.internal_report') },
  { value: 'meeting', label: t('views.finance.templateLib.scenario.meeting') },
  { value: 'system_process', label: t('views.finance.templateLib.scenario.system_process') },
  { value: 'other', label: t('views.finance.templateLib.scenario.other') },
]

const projectStatusOptions: { value: ProjectStatus; label: string }[] = [
  { value: 'preparing', label: t('views.finance.project.statusOptions.preparing') },
  { value: 'materials', label: t('views.finance.project.statusOptions.materials') },
  { value: 'engaging', label: t('views.finance.project.statusOptions.engaging') },
  { value: 'landed', label: t('views.finance.project.statusOptions.landed') },
  { value: 'terminated', label: t('views.finance.project.statusOptions.terminated') },
]

const activeTemplates = computed<Template[]>(() =>
  templateStore.list.filter((tpl) => tpl.is_active),
)

const selectedTemplate = computed<Template | undefined>(() =>
  templateStore.list.find((tpl) => tpl.id === selectedTemplateId.value),
)

const selectedProject = computed<Project | undefined>(() =>
  projectStore.list.find((p) => p.id === selectedProjectId.value),
)

const longTextPlaceholders = computed<Placeholder[]>(() =>
  (selectedTemplate.value?.placeholders || []).filter((p) => p.type === 'long_text'),
)

const canAdvance = computed<boolean>(() => {
  if (active.value === 0) return !!selectedTemplateId.value
  if (active.value === 1) return !!selectedProjectId.value
  if (active.value === 2) {
    if (!selectedTemplate.value) return false
    for (const ph of selectedTemplate.value.placeholders) {
      if (!ph.required) continue
      const val = placeholderValues[ph.key]
      if (val === undefined || val === '' || val === null) return false
    }
    return true
  }
  return true
})

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

const projectStatusTagType = (
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

const stringifyValue = (v: string | number | undefined | null): string => {
  if (v === undefined || v === null) return ''
  return String(v)
}

const truncate = (s: string, limit: number): string =>
  s.length > limit ? `${s.slice(0, limit)}...` : s

// Wrap a raw placeholder key in moustache braces for display, e.g. "foo" → "{{foo}}".
// Built via concatenation to avoid the Vue template parser tripping on the
// literal "{{...}}" in template strings.
const formatKey = (key: string): string => '{' + '{' + key + '}' + '}'

// Display label resolution for a placeholder. Templates uploaded without
// an admin pass through the metadata editor land in the DB with
// ``label == key`` — that's the bare snake-case identifier, which we
// don't want users to see on the fill form. Resolution order:
//   1. ``ph.label`` if the admin actually customised it (label != key);
//   2. an i18n alias table for common finance fields (covers the canonical
//      "立项报告" template + most analogous business templates);
//   3. a generic humanize fallback (snake_case → "Snake Case") for any
//      placeholder we haven't aliased.
// The third branch keeps the form usable for ad-hoc admin templates;
// rolling out a real "edit placeholder label" UI in the template
// management page is the proper long-term fix and is out of scope here.
const humanizeKey = (key: string): string =>
  key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())

const displayLabel = (ph: { key: string; label?: string }): string => {
  const label = (ph.label || '').trim()
  if (label && label !== ph.key) return label
  const aliasKey = `views.finance.documentsLib.wizard.fieldAliases.${ph.key}`
  const aliased = t(aliasKey)
  // vue-i18n returns the key itself when missing; treat that as "no alias".
  if (aliased && aliased !== aliasKey) return aliased
  return humanizeKey(ph.key)
}

const onTemplateScenarioChange = (val: string | number | boolean | undefined) => {
  const filter = (val ?? '') as '' | TemplateScenario
  templateScenarioFilter.value = filter
  templateStore.setScenarioFilter(filter)
  const workspaceId = user.getWorkspaceId()
  if (workspaceId) templateStore.fetchList(workspaceId)
}

const onProjectKeywordInput = (val: string) => {
  projectKeyword.value = val
  projectStore.setKeyword(val)
  debouncedFetchProjects()
}

const debouncedFetchProjects = debounce(() => {
  const workspaceId = user.getWorkspaceId()
  if (workspaceId) projectStore.fetchList(workspaceId)
}, 300)

const onProjectStatusChange = (val: string | undefined) => {
  const s = (val || '') as '' | ProjectStatus
  projectStatusFilter.value = s
  projectStore.setStatusFilter(s)
  const workspaceId = user.getWorkspaceId()
  if (workspaceId) projectStore.fetchList(workspaceId)
}

const goBack = () => {
  router.push({ name: 'finance-documents' })
}

const goToTemplateLibrary = () => {
  router.push({ name: 'finance-template' })
}

const initPlaceholderValues = () => {
  // Reset & seed from current template placeholders, preserving any user edits
  // for unchanged keys would be nice, but switching templates is rare in this
  // flow so we just reset.
  const keys = Object.keys(placeholderValues)
  for (const k of keys) delete placeholderValues[k]
  for (const k of Object.keys(numericValues)) delete numericValues[k]
  if (!selectedTemplate.value) return
  for (const ph of selectedTemplate.value.placeholders) {
    placeholderValues[ph.key] = ''
  }
}

const nextStep = () => {
  if (active.value === 0 && !selectedTemplateId.value) {
    MsgError(t('views.finance.documentsLib.wizard.validation.templateRequired'))
    return
  }
  if (active.value === 1 && !selectedProjectId.value) {
    MsgError(t('views.finance.documentsLib.wizard.validation.projectRequired'))
    return
  }
  if (active.value === 2 && selectedTemplate.value) {
    for (const ph of selectedTemplate.value.placeholders) {
      if (!ph.required) continue
      const val = placeholderValues[ph.key]
      if (val === undefined || val === '' || val === null) {
        MsgError(
          t('views.finance.documentsLib.wizard.validation.placeholderRequired', {
            label: ph.label || ph.key,
          }),
        )
        return
      }
    }
  }
  if (active.value === 0) {
    initPlaceholderValues()
  }
  active.value = Math.min(active.value + 1, 3)
}

const prevStep = () => {
  active.value = Math.max(active.value - 1, 0)
  errorMessage.value = ''
}

const aiFillOne = async (key: string) => {
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId || !selectedTemplateId.value || !selectedProjectId.value) return
  loadingByKey[key] = true
  // Look up the placeholder label so we can surface it in the toast.
  const ph = selectedTemplate.value?.placeholders.find((p) => p.key === key)
  const label = ph ? displayLabel(ph) : key
  try {
    const result = await generationStore.aiFill(
      workspaceId,
      selectedTemplateId.value,
      selectedProjectId.value,
      [key],
    )
    const value = result[key]
    if (value === undefined) {
      // Server returned no entry for this key — treat as fallback.
      MsgWarning(t('views.finance.documentsLib.wizard.aiFillFallback', { label }))
      return
    }
    placeholderValues[key] = value
    if (isAiFallback(value)) {
      MsgWarning(t('views.finance.documentsLib.wizard.aiFillFallback', { label }))
    } else {
      flashKey(key)
      MsgSuccess(t('views.finance.documentsLib.wizard.aiFillOk'))
    }
  } catch {
    MsgWarning(t('views.finance.documentsLib.wizard.aiFillFallback', { label }))
  } finally {
    loadingByKey[key] = false
  }
}

const aiFillAll = async () => {
  const keys = longTextPlaceholders.value.map((p) => p.key)
  if (keys.length === 0) {
    MsgError(t('views.finance.documentsLib.wizard.aiFillEmpty'))
    return
  }
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId || !selectedTemplateId.value || !selectedProjectId.value) return
  aiFillingAll.value = true
  // Mark each long-text field as busy so the per-field spinners also fire.
  for (const k of keys) loadingByKey[k] = true
  try {
    const result = await generationStore.aiFill(
      workspaceId,
      selectedTemplateId.value,
      selectedProjectId.value,
      keys,
    )
    let success = 0
    let skipped = 0
    for (const [k, v] of Object.entries(result)) {
      placeholderValues[k] = v
      if (isAiFallback(v)) {
        skipped += 1
      } else {
        success += 1
        flashKey(k)
      }
    }
    // Keys the server omitted entirely also count as skipped.
    for (const k of keys) {
      if (!(k in result)) skipped += 1
    }
    MsgSuccess(
      t('views.finance.documentsLib.wizard.aiFillSummary', {
        success,
        skipped,
      }),
    )
  } finally {
    aiFillingAll.value = false
    for (const k of keys) loadingByKey[k] = false
  }
}

const handleGenerate = async () => {
  if (!selectedTemplate.value || !selectedProjectId.value) return
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  errorMessage.value = ''
  generating.value = true
  try {
    const payload = {
      template_id: selectedTemplate.value.id,
      project_id: selectedProjectId.value,
      placeholder_values: { ...placeholderValues },
    }
    const created = await generationStore.create(workspaceId, payload)
    if (created) {
      MsgSuccess(t('views.finance.documentsLib.wizard.generateSuccess'))
      router.push({ name: 'finance-documents' })
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
  } finally {
    generating.value = false
  }
}

onMounted(async () => {
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  // Templates & projects with a larger page size for selection convenience.
  templateStore.pageSize = 100
  projectStore.pageSize = 100
  await Promise.all([
    templateStore.fetchList(workspaceId),
    projectStore.fetchList(workspaceId),
  ])
})
</script>

<style lang="scss" scoped>
.finance-wizard {
  // Parent ``.layout-container__right`` is ``overflow: hidden`` (see
  // components/layout-container/index.vue) — router slot children must
  // own their vertical scroll context. Step 3 forms can grow to >12
  // placeholders (financials template = 13), which previously slid the
  // bottom action bar (上一步 / 下一步 / 立即生成) off the bottom of
  // the viewport with no scrollbar. Switching to fixed height +
  // overflow-y restores access to the action bar regardless of form
  // length.
  height: 100%;
  overflow-y: auto;
  background: var(--el-bg-color);

  &__header {
    align-items: center;
  }

  &__title {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
  }

  &__filter-bar {
    display: flex;
    align-items: center;
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  &__select-card {
    cursor: pointer;
    border: 2px solid transparent;
    transition: border-color 0.15s ease;
    &.is-selected {
      border-color: var(--el-color-primary);
    }
  }

  &__select-card-name {
    font-size: 16px;
    font-weight: 600;
    margin: 8px 0 4px;
  }

  &__select-card-meta {
    color: var(--el-text-color-regular);
    font-size: 12px;
  }

  &__empty {
    padding: 48px 0;
    text-align: center;
    color: var(--el-text-color-regular);
  }

  &__muted {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }

  &__key {
    margin-left: 8px;
    background: var(--el-fill-color-light);
    padding: 1px 6px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: var(--el-text-color-secondary);
  }

  &__long-text {
    position: relative;
    border-radius: 4px;
    transition: box-shadow 1s ease;

    &--flash {
      box-shadow: 0 0 0 2px var(--el-color-success);
    }
  }

  &__ai-btn {
    position: absolute;
    top: 4px;
    right: 4px;
    z-index: 1;
  }

  &__hint {
    margin-top: 4px;
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }

  &__summary-title {
    margin: 0 0 12px;
    font-size: 16px;
    font-weight: 600;
  }

  &__values-row {
    margin-bottom: 6px;
    line-height: 1.6;
    strong {
      margin-right: 8px;
    }
  }

  &__values-text {
    color: var(--el-text-color-regular);
    word-break: break-word;
  }

  &__error {
    margin-top: 12px;
    color: var(--el-color-danger);
    font-size: 13px;
  }

  &__footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    // sticky 到视口底部 —— 13+ 字段的长表单滚动时上一步/下一步/生成
    // 按钮始终可见。背景 + 上分隔线 + 阴影避免下方内容透过来。
    position: sticky;
    bottom: 0;
    background: var(--el-bg-color);
    padding: 12px 16px;
    margin: 16px -16px 0;
    border-top: 1px solid var(--el-border-color-lighter);
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
    z-index: 1;
  }
}
</style>

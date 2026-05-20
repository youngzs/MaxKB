<template>
  <el-dialog
    v-model="dialogVisible"
    :title="$t('views.finance.templateLib.uploadDialog.title')"
    width="560"
    append-to-body
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @closed="handleClosed"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      require-asterisk-position="right"
      @submit.prevent
    >
      <el-form-item :label="$t('views.finance.templateLib.fields.name')" prop="name">
        <el-input
          v-model="form.name"
          maxlength="200"
          show-word-limit
          @blur="form.name = form.name.trim()"
        />
      </el-form-item>

      <el-form-item :label="$t('views.finance.templateLib.fields.scenario')" prop="scenario">
        <el-select v-model="form.scenario" style="width: 100%">
          <el-option
            v-for="opt in scenarioOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item :label="$t('views.finance.templateLib.fields.file')" prop="file">
        <el-upload
          ref="uploadRef"
          class="w-full"
          drag
          action="#"
          accept=".docx"
          :auto-upload="false"
          :show-file-list="true"
          :limit="1"
          :file-list="fileList"
          :on-change="onFileChange"
          :on-remove="onFileRemove"
          :on-exceed="onExceed"
        >
          <div class="el-upload__text">
            {{ $t('views.finance.templateLib.uploadDialog.fileDrop') }}
            <em>{{ $t('views.finance.templateLib.uploadDialog.fileClick') }}</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              {{ $t('views.finance.templateLib.uploadDialog.fileTip') }}
            </div>
          </template>
        </el-upload>
      </el-form-item>

      <!--
        占位符语法帮助 + sample 下载。Jinja 字面量（`{{ … }}` / `{% … %}`）
        通过 SYNTAX_EXAMPLES 字符串变量插值进来 —— 双花括号在字符串内
        不会被 Vue 模板编译器二次解析。之前版本在外层用 ``v-pre`` 让
        整块跳过编译，副作用是连 ``v-show`` 也被跳过，面板永远展开。
      -->

      <el-form-item>
        <div class="template-help">
          <div class="template-help__actions">
            <el-button
              type="primary"
              link
              :loading="sampleLoading"
              @click="onDownloadSample"
            >
              <AppIcon iconName="app-download" class="mr-4" />
              {{ $t('views.finance.templateLib.uploadDialog.downloadSample') }}
            </el-button>
            <el-button link @click="helpExpanded = !helpExpanded">
              {{
                helpExpanded
                  ? $t('views.finance.templateLib.uploadDialog.helpCollapse')
                  : $t('views.finance.templateLib.uploadDialog.helpExpand')
              }}
            </el-button>
          </div>

          <transition name="el-collapse-transition">
            <div v-show="helpExpanded" class="template-help__panel">
              <p>
                <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section1Title') }}</strong
                >{{ $t('views.finance.templateLib.uploadDialog.help.section1Desc') }}
              </p>
              <p class="template-help__code">{{ SYNTAX_EXAMPLES.singleVar }}</p>

              <p>
                <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section2Title') }}</strong
                >{{ $t('views.finance.templateLib.uploadDialog.help.section2Desc') }}
              </p>
              <ul>
                <li>
                  <code>{{ $t('views.finance.templateLib.uploadDialog.help.section2NumberKeys') }}</code>
                  → <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section2NumberType') }}</strong>
                </li>
                <li>
                  <code>{{ $t('views.finance.templateLib.uploadDialog.help.section2DateKeys') }}</code>
                  → <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section2DateType') }}</strong>
                </li>
                <li>
                  <code>{{ $t('views.finance.templateLib.uploadDialog.help.section2LongTextKeys') }}</code>
                  → <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section2LongTextType') }}</strong>
                </li>
                <li>
                  {{ $t('views.finance.templateLib.uploadDialog.help.section2OtherKeys') }}
                  → <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section2OtherType') }}</strong>
                </li>
              </ul>

              <p>
                <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section3Title') }}</strong
                >{{ $t('views.finance.templateLib.uploadDialog.help.section3Desc') }}
              </p>
              <p class="template-help__code">{{ SYNTAX_EXAMPLES.cond }}</p>

              <p>
                <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section4Title') }}</strong
                >{{ $t('views.finance.templateLib.uploadDialog.help.section4Desc') }}
              </p>
              <p class="template-help__code">{{ SYNTAX_EXAMPLES.loop }}</p>

              <p>
                <strong>{{ $t('views.finance.templateLib.uploadDialog.help.section5Title') }}</strong
                >{{ $t('views.finance.templateLib.uploadDialog.help.section5Desc') }}
              </p>
              <p class="template-help__code">{{ SYNTAX_EXAMPLES.filter }}</p>

              <p style="color: var(--el-color-warning); margin-top: 8px">
                {{ $t('views.finance.templateLib.uploadDialog.help.warning') }}
              </p>
            </div>
          </transition>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button :disabled="loading" @click="dialogVisible = false">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          {{ $t('views.finance.templateLib.uploadDialog.submit') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules, UploadFile, UploadFiles } from 'element-plus'
import { MsgError, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import type { Template, TemplateScenario } from '@/api/finance/type'
import { downloadSampleTemplate } from '@/api/finance/template'

interface Props {
  modelValue: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', tpl: Template): void
}>()

const { user, financeTemplate } = useStore()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const formRef = ref<FormInstance>()
const uploadRef = ref<{ clearFiles: () => void } | null>(null)
const loading = ref(false)
const sampleLoading = ref(false)
const helpExpanded = ref(false)

// Jinja literal examples shown inside the syntax help panel.
//
// We feed them in as plain JS strings so Vue's template compiler treats
// each `{{ ... }}` / `{% ... %}` as plain text inside an interpolation
// rather than as a nested Vue expression. The previous workaround was
// to wrap the panel in ``v-pre``, but that also disables ``v-show`` on
// the same element, leaving the panel permanently expanded — the bug
// this constant is meant to fix.
const SYNTAX_EXAMPLES = {
  singleVar: '项目名称：{{ project_name }}',
  cond: '{% if has_collateral %}有抵押{% else %}无抵押{% endif %}',
  loop: '{% for name in material_names %}• {{ name }}{% endfor %}',
  filter: '金额：{{ amount | round(2) }} 元',
}

async function onDownloadSample() {
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  sampleLoading.value = true
  try {
    await downloadSampleTemplate(workspaceId)
  } finally {
    sampleLoading.value = false
  }
}

interface UploadForm {
  name: string
  scenario: TemplateScenario
  file: File | null
}

const emptyForm = (): UploadForm => ({
  name: '',
  scenario: 'internal_report',
  file: null,
})

const form = reactive<UploadForm>(emptyForm())
const fileList = ref<UploadFiles>([])

const scenarioOptions: { value: TemplateScenario; label: string }[] = [
  { value: 'internal_report', label: t('views.finance.templateLib.scenario.internal_report') },
  { value: 'meeting', label: t('views.finance.templateLib.scenario.meeting') },
  { value: 'system_process', label: t('views.finance.templateLib.scenario.system_process') },
  { value: 'other', label: t('views.finance.templateLib.scenario.other') },
]

const MAX_SIZE_BYTES = 10 * 1024 * 1024

const validateFile = (file: File): boolean => {
  if (!file.name.toLowerCase().endsWith('.docx')) {
    MsgError(t('views.finance.templateLib.validation.fileType'))
    return false
  }
  if (file.size > MAX_SIZE_BYTES) {
    MsgError(t('views.finance.templateLib.validation.fileSize'))
    return false
  }
  return true
}

const rules = reactive<FormRules<UploadForm>>({
  name: [
    {
      required: true,
      message: t('views.finance.templateLib.validation.nameRequired'),
      trigger: 'blur',
    },
  ],
  scenario: [
    {
      required: true,
      message: t('views.finance.templateLib.validation.scenarioRequired'),
      trigger: 'change',
    },
  ],
  file: [
    {
      validator: (_rule, _value, callback) => {
        if (!form.file) {
          callback(new Error(t('views.finance.templateLib.validation.fileRequired')))
          return
        }
        callback()
      },
      trigger: 'change',
    },
  ],
})

const onFileChange = (uploadFile: UploadFile, uploadFiles: UploadFiles) => {
  const raw = uploadFile.raw as File | undefined
  if (!raw) return
  if (!validateFile(raw)) {
    fileList.value = uploadFiles.filter((f) => f.uid !== uploadFile.uid)
    return
  }
  form.file = raw
  fileList.value = [uploadFile]
  if (!form.name) {
    // Pre-fill name from file basename (without extension) for convenience.
    form.name = raw.name.replace(/\.docx$/i, '')
  }
  formRef.value?.validateField('file').catch(() => undefined)
}

const onFileRemove = () => {
  form.file = null
  fileList.value = []
}

const onExceed = (files: File[]) => {
  // Replace existing file when the user picks another.
  const f = files[0]
  if (!validateFile(f)) return
  fileList.value = [
    {
      name: f.name,
      uid: Date.now(),
      status: 'ready',
      raw: f,
      size: f.size,
    } as unknown as UploadFile,
  ]
  form.file = f
  if (!form.name) {
    form.name = f.name.replace(/\.docx$/i, '')
  }
  formRef.value?.validateField('file').catch(() => undefined)
}

const handleClosed = () => {
  Object.assign(form, emptyForm())
  fileList.value = []
  formRef.value?.clearValidate()
  uploadRef.value?.clearFiles?.()
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      Object.assign(form, emptyForm())
      fileList.value = []
      formRef.value?.clearValidate()
    }
  },
)

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid || !form.file) return
    const workspaceId = user.getWorkspaceId()
    if (!workspaceId) return
    loading.value = true
    try {
      const created = await financeTemplate.upload(
        workspaceId,
        form.file,
        form.name.trim(),
        form.scenario,
      )
      if (created) {
        MsgSuccess(t('views.finance.templateLib.uploadSuccess'))
        emit('success', created)
        dialogVisible.value = false
      }
    } finally {
      loading.value = false
    }
  })
}
</script>

<style lang="scss" scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.template-help {
  width: 100%;
  &__actions {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  &__panel {
    margin-top: 8px;
    padding: 12px 16px;
    background: var(--el-fill-color-light);
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.7;
    p {
      margin: 4px 0;
    }
    ul {
      margin: 4px 0 8px 20px;
    }
    code {
      background: var(--el-fill-color);
      padding: 1px 4px;
      border-radius: 3px;
      font-family: 'Courier New', monospace;
    }
  }
  &__code {
    font-family: 'Courier New', monospace;
    background: var(--el-fill-color);
    padding: 4px 8px;
    border-radius: 3px;
    display: inline-block;
  }
}
</style>

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

      <!-- 占位符语法帮助 + sample 下载。`v-pre` 跳过 Vue 模板插值，
           这样 `{{ project_name }}` 这种 Jinja 字面量才能原样渲染。 -->
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
              下载示例模板（.docx）
            </el-button>
            <el-button link @click="helpExpanded = !helpExpanded">
              {{ helpExpanded ? '收起' : '展开' }}占位符语法
            </el-button>
          </div>

          <transition name="el-collapse-transition">
            <div v-show="helpExpanded" class="template-help__panel" v-pre>
              <p><strong>1. 单变量替换</strong> —— 用双花括号包裹变量名，前后留空格：</p>
              <p class="template-help__code">项目名称：{{ project_name }}</p>

              <p><strong>2. 变量后缀决定字段类型</strong>（上传后可在详情页改）：</p>
              <ul>
                <li><code>*_amount / *_count / *_number / *_total</code> → <strong>number</strong></li>
                <li><code>*_date / *_at / *_time / *_deadline</code> → <strong>date</strong></li>
                <li><code>*_desc / *_summary / *_analysis / *_notes / *_content</code> → <strong>long_text</strong></li>
                <li>其他 → <strong>text</strong></li>
              </ul>

              <p><strong>3. 条件块</strong>（同一段落里整段同一字体，否则跨 run 会解析失败）：</p>
              <p class="template-help__code">{% if has_collateral %}有抵押{% else %}无抵押{% endif %}</p>

              <p><strong>4. 循环</strong>（推荐传字符串数组，避免 <code>item.name</code> 这种属性访问）：</p>
              <p class="template-help__code">{% for name in material_names %}• {{ name }}{% endfor %}</p>

              <p><strong>5. 过滤器</strong>（Jinja 标准）：</p>
              <p class="template-help__code">金额：{{ amount | round(2) }} 元</p>

              <p style="color: var(--el-color-warning); margin-top: 8px">
                ⚠️ 进阶语法（条件/循环/过滤器/属性访问）必须把整段表达式放在 Word 里同一 run 内
                —— 在 Word 中选中整段后重设为同一字体即可。否则 docxtpl 会跨 run 拼接 XML，
                极易撞 <code>unexpected '.'</code> 等解析错误。
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

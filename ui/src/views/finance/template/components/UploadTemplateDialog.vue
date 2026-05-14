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
</style>

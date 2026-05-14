<template>
  <el-dialog
    v-model="dialogVisible"
    :title="$t('views.finance.materials.create.title')"
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
      <el-form-item
        :label="$t('views.finance.materials.create.project')"
        prop="project_id"
      >
        <el-select
          v-model="form.project_id"
          filterable
          style="width: 100%"
          :placeholder="$t('views.finance.materials.create.project')"
        >
          <el-option
            v-for="p in projectStore.list"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item
        :label="$t('views.finance.materials.create.titleField')"
        prop="title"
      >
        <el-input
          v-model="form.title"
          maxlength="200"
          show-word-limit
          :placeholder="$t('views.finance.materials.create.titlePlaceholder')"
          @blur="form.title = form.title.trim()"
        />
      </el-form-item>

      <el-form-item :label="$t('views.finance.materials.create.mode')">
        <el-radio-group v-model="form.mode">
          <el-radio value="text">
            {{ $t('views.finance.materials.create.pasteText') }}
          </el-radio>
          <el-radio value="file">
            {{ $t('views.finance.materials.create.uploadFile') }}
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item
        v-if="form.mode === 'text'"
        prop="requirement_text"
        :rules="textRule"
      >
        <el-input
          v-model="form.requirement_text"
          type="textarea"
          :rows="10"
          :placeholder="
            $t('views.finance.materials.create.requirementPlaceholder')
          "
          resize="vertical"
        />
      </el-form-item>

      <el-form-item v-else prop="file" :rules="fileRule">
        <el-upload
          ref="uploadRef"
          class="w-full"
          drag
          action="#"
          accept=".txt,.docx,.pdf"
          :auto-upload="false"
          :show-file-list="true"
          :limit="1"
          :file-list="fileList"
          :on-change="onFileChange"
          :on-remove="onFileRemove"
          :on-exceed="onExceed"
        >
          <div class="el-upload__text">
            {{ $t('views.finance.materials.create.fileDrop') }}
            <em>{{ $t('views.finance.materials.create.fileClick') }}</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              {{ $t('views.finance.materials.create.fileHint') }}
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
          {{ $t('views.finance.materials.create.submit') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules, UploadFile, UploadFiles } from 'element-plus'
import { MsgError, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import type { MaterialsTask } from '@/api/finance/type'

interface Props {
  modelValue: boolean
  /** Optional preselected project id when opened from a project detail page. */
  defaultProjectId?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', task: MaterialsTask): void
}>()

const router = useRouter()
const {
  user,
  financeProject: projectStore,
  financeMaterials: materialsStore,
} = useStore()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const formRef = ref<FormInstance>()
const uploadRef = ref<{ clearFiles: () => void } | null>(null)
const loading = ref(false)

interface CreateForm {
  project_id: string
  title: string
  mode: 'text' | 'file'
  requirement_text: string
  file: File | null
}

const emptyForm = (): CreateForm => ({
  project_id: props.defaultProjectId || '',
  title: '',
  mode: 'text',
  requirement_text: '',
  file: null,
})

const form = reactive<CreateForm>(emptyForm())
const fileList = ref<UploadFiles>([])

const MAX_SIZE_BYTES = 5 * 1024 * 1024
const ALLOWED_EXTS = ['.txt', '.docx', '.pdf']

const validateFile = (file: File): boolean => {
  const lower = file.name.toLowerCase()
  if (!ALLOWED_EXTS.some((ext) => lower.endsWith(ext))) {
    MsgError(t('views.finance.materials.validation.fileTypeInvalid'))
    return false
  }
  if (file.size > MAX_SIZE_BYTES) {
    MsgError(t('views.finance.materials.validation.fileSizeExceeded'))
    return false
  }
  return true
}

const textRule = [
  {
    validator: (
      _rule: unknown,
      _value: unknown,
      callback: (err?: Error) => void,
    ) => {
      if (form.mode !== 'text') {
        callback()
        return
      }
      if (!form.requirement_text || !form.requirement_text.trim()) {
        callback(
          new Error(t('views.finance.materials.validation.requirementRequired')),
        )
        return
      }
      callback()
    },
    trigger: 'blur',
  },
]

const fileRule = [
  {
    validator: (
      _rule: unknown,
      _value: unknown,
      callback: (err?: Error) => void,
    ) => {
      if (form.mode !== 'file') {
        callback()
        return
      }
      if (!form.file) {
        callback(
          new Error(t('views.finance.materials.validation.requirementRequired')),
        )
        return
      }
      callback()
    },
    trigger: 'change',
  },
]

const rules = reactive<FormRules<CreateForm>>({
  project_id: [
    {
      required: true,
      message: t('views.finance.materials.validation.projectRequired'),
      trigger: 'change',
    },
  ],
  title: [
    {
      required: true,
      message: t('views.finance.materials.validation.titleRequired'),
      trigger: 'blur',
    },
    {
      max: 200,
      message: t('views.finance.materials.validation.titleTooLong'),
      trigger: 'blur',
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
  formRef.value?.validateField('file').catch(() => undefined)
}

const onFileRemove = () => {
  form.file = null
  fileList.value = []
}

const onExceed = (files: File[]) => {
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
      // Make sure the project select has options. The list might be empty if
      // the user landed directly on /finance/materials without visiting the
      // project page first.
      const wid = user.getWorkspaceId()
      if (wid && projectStore.list.length === 0) {
        projectStore.fetchList(wid).catch(() => undefined)
      }
    }
  },
)

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    const workspaceId = user.getWorkspaceId()
    if (!workspaceId) return
    loading.value = true
    try {
      const created = await materialsStore.create(workspaceId, {
        project_id: form.project_id,
        title: form.title.trim(),
        requirement_text:
          form.mode === 'text' ? form.requirement_text : undefined,
        file: form.mode === 'file' && form.file ? form.file : undefined,
      })
      if (created) {
        MsgSuccess(t('views.finance.materials.create.success'))
        emit('success', created)
        dialogVisible.value = false
        // Fire-and-forget parse trigger, then navigate to detail page.
        materialsStore
          .triggerParse(workspaceId, created.id)
          .catch(() => undefined)
        router.push({
          name: 'finance-materials-detail',
          params: { pk: created.id },
        })
      }
    } finally {
      loading.value = false
    }
  })
}

onMounted(() => {
  const wid = user.getWorkspaceId()
  if (wid && projectStore.list.length === 0) {
    projectStore.fetchList(wid).catch(() => undefined)
  }
})
</script>

<style lang="scss" scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>

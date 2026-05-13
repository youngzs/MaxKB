<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? $t('views.finance.project.editProject') : $t('views.finance.project.newProject')"
    width="640"
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
      <el-form-item :label="$t('views.finance.project.fields.name')" prop="name">
        <el-input
          v-model="form.name"
          maxlength="200"
          :placeholder="$t('views.finance.project.placeholders.name')"
          show-word-limit
          @blur="form.name = form.name?.trim()"
        />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item :label="$t('views.finance.project.fields.projectType')" prop="project_type">
            <el-select
              v-model="form.project_type"
              :placeholder="$t('views.finance.project.placeholders.projectType')"
              style="width: 100%"
            >
              <el-option
                v-for="opt in projectTypeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item :label="$t('views.finance.project.fields.code')" prop="code">
            <el-input
              v-model="form.code"
              maxlength="64"
              :placeholder="$t('views.finance.project.placeholders.code')"
              show-word-limit
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item :label="$t('views.finance.project.fields.status')">
            <el-select
              v-model="form.status"
              :placeholder="$t('views.finance.project.placeholders.status')"
              style="width: 100%"
            >
              <el-option
                v-for="opt in statusOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item :label="$t('views.finance.project.fields.region')">
            <el-input
              v-model="form.region"
              :placeholder="$t('views.finance.project.placeholders.region')"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item :label="$t('views.finance.project.fields.targetAmount')">
            <el-input-number
              v-model="targetAmountNumber"
              :min="0"
              :precision="2"
              :step="10000"
              :placeholder="$t('views.finance.project.placeholders.targetAmount')"
              style="width: 100%"
              controls-position="right"
            />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item :label="$t('views.finance.project.fields.currency')">
            <el-select v-model="form.currency" style="width: 100%">
              <el-option label="CNY" value="CNY" />
              <el-option label="USD" value="USD" />
              <el-option label="EUR" value="EUR" />
              <el-option label="HKD" value="HKD" />
              <el-option label="JPY" value="JPY" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item :label="$t('views.finance.project.fields.industryCode')">
            <el-input
              v-model="form.industry_code"
              :placeholder="$t('views.finance.project.placeholders.industryCode')"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item :label="$t('views.finance.project.fields.knowledgeBaseIds')">
        <el-select
          v-model="form.knowledge_base_ids"
          multiple
          disabled
          :placeholder="$t('views.finance.project.knowledgeBasePending')"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item :label="$t('views.finance.project.fields.description')">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          maxlength="2000"
          :placeholder="$t('views.finance.project.placeholders.description')"
          show-word-limit
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogVisible = false" :loading="loading">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          {{ isEdit ? $t('common.save') : $t('common.create') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import type { Project, ProjectInput, ProjectStatus, ProjectType } from '@/api/finance/type'

interface Props {
  modelValue: boolean
  initial?: Project | null
}

const props = withDefaults(defineProps<Props>(), {
  initial: null,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', project: Project): void
}>()

const { user, financeProject } = useStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const isEdit = computed(() => !!props.initial)

const emptyForm = (): ProjectInput => ({
  name: '',
  code: '',
  project_type: 'bank_loan',
  status: 'preparing',
  target_amount: '',
  currency: 'CNY',
  region: '',
  industry_code: '',
  knowledge_base_ids: [],
  description: '',
})

const form = ref<ProjectInput>(emptyForm())

const targetAmountNumber = computed<number | undefined>({
  get() {
    const raw = form.value.target_amount
    if (raw === '' || raw === null || raw === undefined) return undefined
    const num = Number(raw)
    return Number.isFinite(num) ? num : undefined
  },
  set(val) {
    form.value.target_amount = val === undefined || val === null ? '' : String(val)
  },
})

const projectTypeOptions: { value: ProjectType; label: string }[] = [
  { value: 'bank_loan', label: t('views.finance.project.projectType.bank_loan') },
  { value: 'bond', label: t('views.finance.project.projectType.bond') },
  { value: 'trust', label: t('views.finance.project.projectType.trust') },
  { value: 'abs', label: t('views.finance.project.projectType.abs') },
  { value: 'other', label: t('views.finance.project.projectType.other') },
]

const statusOptions: { value: ProjectStatus; label: string }[] = [
  { value: 'preparing', label: t('views.finance.project.statusOptions.preparing') },
  { value: 'materials', label: t('views.finance.project.statusOptions.materials') },
  { value: 'engaging', label: t('views.finance.project.statusOptions.engaging') },
  { value: 'landed', label: t('views.finance.project.statusOptions.landed') },
  { value: 'terminated', label: t('views.finance.project.statusOptions.terminated') },
]

const rules = reactive<FormRules<ProjectInput>>({
  name: [
    {
      required: true,
      message: t('views.finance.project.validation.nameRequired'),
      trigger: 'blur',
    },
    {
      max: 200,
      message: t('views.finance.project.validation.nameTooLong'),
      trigger: 'blur',
    },
  ],
  project_type: [
    {
      required: true,
      message: t('views.finance.project.validation.typeRequired'),
      trigger: 'change',
    },
  ],
  code: [
    {
      max: 64,
      message: t('views.finance.project.validation.codeTooLong'),
      trigger: 'blur',
    },
    {
      pattern: /^[A-Za-z0-9-]*$/,
      message: t('views.finance.project.validation.codeFormat'),
      trigger: 'blur',
    },
  ],
})

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      if (props.initial) {
        const init = props.initial
        form.value = {
          name: init.name,
          code: init.code,
          project_type: init.project_type,
          status: init.status,
          target_amount: init.target_amount ?? '',
          currency: init.currency || 'CNY',
          region: init.region,
          industry_code: init.industry_code,
          knowledge_base_ids: [...(init.knowledge_base_ids || [])],
          description: init.description,
        }
      } else {
        form.value = emptyForm()
      }
      formRef.value?.clearValidate()
    }
  },
)

const handleClosed = () => {
  form.value = emptyForm()
  formRef.value?.clearValidate()
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    const workspaceId = user.getWorkspaceId()
    if (!workspaceId) return

    const payload: ProjectInput = {
      ...form.value,
      name: form.value.name.trim(),
      target_amount:
        form.value.target_amount === '' || form.value.target_amount === undefined
          ? null
          : form.value.target_amount,
    }

    loading.value = true
    try {
      let saved: Project | undefined
      if (isEdit.value && props.initial) {
        saved = await financeProject.update(workspaceId, props.initial.id, payload)
        if (saved) MsgSuccess(t('common.saveSuccess'))
      } else {
        saved = await financeProject.create(workspaceId, payload)
        if (saved) MsgSuccess(t('common.createSuccess'))
      }
      if (saved) {
        emit('success', saved)
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

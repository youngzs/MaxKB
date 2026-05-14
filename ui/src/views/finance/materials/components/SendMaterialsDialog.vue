<template>
  <el-dialog
    v-model="visibleProxy"
    :title="$t('views.finance.send.dialog.title')"
    width="780px"
    destroy-on-close
    @open="onOpen"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
    >
      <el-form-item :label="$t('views.finance.send.form.to')" prop="toAddresses">
        <el-select
          v-model="form.toAddresses"
          multiple
          filterable
          allow-create
          default-first-option
          :placeholder="$t('views.finance.send.form.toPlaceholder')"
          style="width: 100%"
          no-data-text=" "
        />
      </el-form-item>
      <el-form-item :label="$t('views.finance.send.form.cc')">
        <el-select
          v-model="form.ccAddresses"
          multiple
          filterable
          allow-create
          default-first-option
          :placeholder="$t('views.finance.send.form.ccPlaceholder')"
          style="width: 100%"
          no-data-text=" "
        />
      </el-form-item>
      <div class="flex" style="gap: 12px">
        <el-form-item
          :label="$t('views.finance.send.form.smtp')"
          prop="smtpConfigId"
          style="flex: 1"
        >
          <el-select
            v-model="form.smtpConfigId"
            :placeholder="$t('views.finance.send.form.smtpPlaceholder')"
            style="width: 100%"
            @change="updatePreview"
          >
            <el-option
              v-for="opt in smtpOptions"
              :key="opt.id"
              :value="opt.id"
              :label="`${opt.name} <${opt.from_email}>${opt.is_default ? ' ★' : ''}`"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          :label="$t('views.finance.send.form.template')"
          prop="emailTemplateId"
          style="flex: 1"
        >
          <el-select
            v-model="form.emailTemplateId"
            :placeholder="$t('views.finance.send.form.templatePlaceholder')"
            style="width: 100%"
            @change="updatePreview"
          >
            <el-option
              v-for="opt in templateOptions"
              :key="opt.id"
              :value="opt.id"
              :label="opt.name"
            />
          </el-select>
        </el-form-item>
      </div>

      <el-form-item>
        <el-checkbox v-model="form.attachZip">
          {{ $t('views.finance.send.form.attachZip') }}
        </el-checkbox>
      </el-form-item>

      <el-divider />
      <p class="finance-send__preview-title">
        {{ $t('views.finance.send.preview.title') }}
      </p>
      <div class="finance-send__preview">
        <div class="finance-send__preview-row">
          <span class="finance-send__preview-label">
            {{ $t('views.finance.send.preview.subject') }}
          </span>
          <span class="finance-send__preview-value">
            {{ previewSubject || '-' }}
          </span>
        </div>
        <pre class="finance-send__preview-body">{{ previewBody || '-' }}</pre>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="visibleProxy = false">{{ $t('common.cancel') }}</el-button>
      <el-button
        type="primary"
        :loading="sending"
        :disabled="!form.smtpConfigId || !form.emailTemplateId"
        @click="onSubmit"
      >
        {{ $t('views.finance.send.actions.send') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { MsgError, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { listSmtpConfigs } from '@/api/finance/smtp-config'
import { listEmailTemplates } from '@/api/finance/email-template'
import { sendMaterialsTask } from '@/api/finance/email-send'
import type {
  EmailTemplate,
  MaterialsTask,
  SmtpConfig,
} from '@/api/finance/type'

const props = defineProps<{
  visible: boolean
  task: MaterialsTask | null
  projectName: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'sent'): void
}>()

const { user } = useStore()

const visibleProxy = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const formRef = ref<FormInstance>()
const smtpOptions = ref<SmtpConfig[]>([])
const templateOptions = ref<EmailTemplate[]>([])
const sending = ref(false)

const form = reactive<{
  toAddresses: string[]
  ccAddresses: string[]
  smtpConfigId: string
  emailTemplateId: string
  attachZip: boolean
}>({
  toAddresses: [],
  ccAddresses: [],
  smtpConfigId: '',
  emailTemplateId: '',
  attachZip: true,
})

const rules: FormRules = {
  toAddresses: [
    {
      required: true,
      validator: (_rule, value: string[], callback) => {
        if (!value || value.length === 0) {
          callback(new Error(t('views.finance.send.validation.toRequired')))
        } else if (
          value.some(
            (v) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
          )
        ) {
          callback(new Error(t('views.finance.send.validation.toInvalid')))
        } else {
          callback()
        }
      },
      trigger: 'change',
    },
  ],
  smtpConfigId: [
    {
      required: true,
      message: t('views.finance.send.validation.smtpRequired'),
      trigger: 'change',
    },
  ],
  emailTemplateId: [
    {
      required: true,
      message: t('views.finance.send.validation.templateRequired'),
      trigger: 'change',
    },
  ],
}

const VAR_RE = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}/g

const buildContext = (): Record<string, string> => {
  const firstTo = form.toAddresses[0] || ''
  const recipient = firstTo.includes('@') ? firstTo.split('@')[0] : firstTo
  return {
    project_name: props.projectName || '',
    task_title: props.task?.title || '',
    recipient_name: recipient,
    zip_filename: props.task ? `materials-${props.task.id}.zip` : '',
  }
}

const renderTemplate = (text: string, ctx: Record<string, string>): string =>
  (text || '').replace(VAR_RE, (_m, key) => ctx[key] ?? '')

const selectedTemplate = computed<EmailTemplate | null>(
  () => templateOptions.value.find((x) => x.id === form.emailTemplateId) || null,
)

const previewSubject = computed(() =>
  selectedTemplate.value
    ? renderTemplate(selectedTemplate.value.subject, buildContext())
    : '',
)
const previewBody = computed(() =>
  selectedTemplate.value
    ? renderTemplate(selectedTemplate.value.body_text, buildContext())
    : '',
)

const updatePreview = () => {
  // Force re-render of preview; computed deps already cover it but keep
  // the handler explicit for future extensibility.
}

const fetchSupportRows = async () => {
  const wid = user.getWorkspaceId()
  if (!wid) return
  const [smtpRes, tplRes] = await Promise.all([
    listSmtpConfigs(wid, { size: 100 }),
    listEmailTemplates(wid, { size: 100 }),
  ])
  smtpOptions.value = (smtpRes.data?.records as SmtpConfig[]) || []
  templateOptions.value = (tplRes.data?.records as EmailTemplate[]) || []
  // Pre-select defaults
  const defaultSmtp = smtpOptions.value.find((c) => c.is_default)
  if (defaultSmtp) form.smtpConfigId = defaultSmtp.id
  const defaultTpl = templateOptions.value.find(
    (t1) => t1.scenario === 'materials' && t1.is_active,
  )
  if (defaultTpl) form.emailTemplateId = defaultTpl.id
}

const onOpen = async () => {
  form.toAddresses = []
  form.ccAddresses = []
  form.smtpConfigId = ''
  form.emailTemplateId = ''
  form.attachZip = true
  await fetchSupportRows()
}

const onSubmit = async () => {
  if (!formRef.value) return
  if (!props.task) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    const wid = user.getWorkspaceId()
    if (!wid || !props.task) return
    sending.value = true
    try {
      const res = await sendMaterialsTask(wid, props.task.id, {
        smtp_config_id: form.smtpConfigId,
        email_template_id: form.emailTemplateId,
        to_addresses: form.toAddresses,
        cc_addresses: form.ccAddresses,
        attach_zip: form.attachZip,
      })
      if (res.data?.status === 'sent') {
        MsgSuccess(t('views.finance.send.sendSuccess'))
        emit('sent')
        visibleProxy.value = false
      } else {
        MsgError(
          t('views.finance.send.sendFailed') +
            (res.data?.error_message ? `: ${res.data.error_message}` : ''),
        )
      }
    } finally {
      sending.value = false
    }
  })
}
</script>

<style lang="scss" scoped>
.finance-send {
  &__preview-title {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    margin: 0 0 8px;
  }
  &__preview {
    background: var(--el-fill-color-light);
    padding: 12px 16px;
    border-radius: 4px;
  }
  &__preview-row {
    margin-bottom: 8px;
    font-size: 13px;
  }
  &__preview-label {
    color: var(--el-text-color-secondary);
    margin-right: 8px;
  }
  &__preview-body {
    margin: 8px 0 0;
    font-size: 13px;
    color: var(--el-text-color-regular);
    white-space: pre-wrap;
    font-family: inherit;
    max-height: 200px;
    overflow: auto;
  }
}
</style>

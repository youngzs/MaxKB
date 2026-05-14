<template>
  <el-dialog
    v-model="visibleProxy"
    :title="
      resultPanel
        ? $t('views.finance.send.sentTitle')
        : $t('views.finance.send.dialog.title')
    "
    width="780px"
    destroy-on-close
    @open="onOpen"
    @closed="onClosed"
  >
    <!-- Result panel — shown after send completes, replaces the form. -->
    <div v-if="resultPanel" class="finance-send__result">
      <div
        v-if="resultPanel.status === 'sent'"
        class="finance-send__result-banner finance-send__result-banner--ok"
      >
        {{
          $t('views.finance.send.sentAll', {
            n: resultPanel.recipients.length,
          })
        }}
      </div>
      <div
        v-else
        class="finance-send__result-banner finance-send__result-banner--err"
      >
        <strong>{{ $t('views.finance.send.sentFailed') }}</strong>
        <p
          v-if="resultPanel.errorMessage"
          class="finance-send__result-error-msg"
        >
          {{ resultPanel.errorMessage }}
        </p>
      </div>
      <ul class="finance-send__result-list">
        <li
          v-for="(addr, idx) in resultPanel.recipients"
          :key="`${addr}-${idx}`"
          class="finance-send__result-item"
        >
          <el-icon
            v-if="resultPanel.status === 'sent'"
            class="finance-send__result-icon finance-send__result-icon--ok"
          >
            <Check />
          </el-icon>
          <el-icon
            v-else
            class="finance-send__result-icon finance-send__result-icon--err"
          >
            <Close />
          </el-icon>
          <span class="finance-send__result-addr">{{ addr }}</span>
          <span class="finance-send__result-kind">{{ resultPanel.kinds[idx] }}</span>
        </li>
      </ul>
    </div>

    <el-form
      v-else
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
      <!-- Result mode: retry on failure + explicit close (no auto-close). -->
      <template v-if="resultPanel">
        <el-button
          v-if="resultPanel.status !== 'sent'"
          :loading="sending"
          type="primary"
          @click="onRetry"
        >
          {{ $t('views.finance.send.retry') }}
        </el-button>
        <el-button @click="visibleProxy = false">
          {{ $t('common.close') }}
        </el-button>
      </template>
      <!-- Form mode: standard cancel / send. -->
      <template v-else>
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
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { Check, Close } from '@element-plus/icons-vue'
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

/** Internal shape used by the result panel — the backend currently returns a
 *  single combined status for the whole send, so we mirror that status across
 *  every recipient (to/cc) for now and tag each with its kind. */
interface SendResult {
  status: 'sent' | 'failed'
  recipients: string[]
  /** Parallel to `recipients`: 'to' | 'cc'. */
  kinds: string[]
  errorMessage?: string
}

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
/** Non-null after the first send attempt; controls the result-panel UI. */
const resultPanel = ref<SendResult | null>(null)

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
  resultPanel.value = null
  await fetchSupportRows()
}

/** Reset the result panel state once Element Plus finishes the close
 *  animation, so the next opening starts in form mode. */
const onClosed = () => {
  resultPanel.value = null
}

/** Perform the actual send request, building the result-panel state from
 *  the response. Splitting it out lets the "Retry" button reuse it. */
const performSend = async () => {
  if (!props.task) return
  const wid = user.getWorkspaceId()
  if (!wid) return
  sending.value = true
  try {
    const res = await sendMaterialsTask(wid, props.task.id, {
      smtp_config_id: form.smtpConfigId,
      email_template_id: form.emailTemplateId,
      to_addresses: form.toAddresses,
      cc_addresses: form.ccAddresses,
      attach_zip: form.attachZip,
    })
    const recipients: string[] = [
      ...form.toAddresses,
      ...form.ccAddresses,
    ]
    const kinds: string[] = [
      ...form.toAddresses.map(() => t('views.finance.send.form.to')),
      ...form.ccAddresses.map(() => t('views.finance.send.form.cc')),
    ]
    if (res.data?.status === 'sent') {
      resultPanel.value = {
        status: 'sent',
        recipients,
        kinds,
      }
      emit('sent')
    } else {
      resultPanel.value = {
        status: 'failed',
        recipients,
        kinds,
        errorMessage: res.data?.error_message || '',
      }
    }
  } catch (err) {
    // Network / server error — surface as a failed result panel so the user
    // can retry without re-entering the form.
    const message = err instanceof Error ? err.message : String(err)
    resultPanel.value = {
      status: 'failed',
      recipients: [...form.toAddresses, ...form.ccAddresses],
      kinds: [
        ...form.toAddresses.map(() => t('views.finance.send.form.to')),
        ...form.ccAddresses.map(() => t('views.finance.send.form.cc')),
      ],
      errorMessage: message,
    }
  } finally {
    sending.value = false
  }
}

const onSubmit = async () => {
  if (!formRef.value) return
  if (!props.task) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    await performSend()
  })
}

/** Resubmit using the same form values; the result panel toggles back to
 *  the in-flight indicator via the button's `:loading` binding. */
const onRetry = () => {
  performSend()
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

  &__result {
    padding: 4px 0 8px;
  }

  &__result-banner {
    padding: 12px 16px;
    border-radius: 4px;
    margin-bottom: 16px;
    font-size: 14px;
    line-height: 1.5;

    &--ok {
      background: var(--el-color-success-light-9);
      color: var(--el-color-success-dark-2);
      border: 1px solid var(--el-color-success-light-5);
    }

    &--err {
      background: var(--el-color-danger-light-9);
      color: var(--el-color-danger-dark-2);
      border: 1px solid var(--el-color-danger-light-5);
    }
  }

  &__result-error-msg {
    margin: 6px 0 0;
    font-size: 13px;
    white-space: pre-wrap;
    word-break: break-word;
  }

  &__result-list {
    list-style: none;
    margin: 0;
    padding: 0;
    max-height: 280px;
    overflow-y: auto;
  }

  &__result-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--el-border-color-lighter);
    font-size: 13px;

    &:last-child {
      border-bottom: none;
    }
  }

  &__result-icon {
    font-size: 16px;
    flex-shrink: 0;

    &--ok {
      color: var(--el-color-success);
    }

    &--err {
      color: var(--el-color-danger);
    }
  }

  &__result-addr {
    flex: 1;
    color: var(--el-text-color-primary);
    word-break: break-all;
  }

  &__result-kind {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    padding: 1px 8px;
    background: var(--el-fill-color);
    border-radius: 10px;
  }
}
</style>

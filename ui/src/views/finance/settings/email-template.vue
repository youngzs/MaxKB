<template>
  <div class="finance-email-template p-24">
    <div class="finance-email-template__header flex-between mb-16">
      <h2 class="finance-email-template__title">
        {{ $t('views.finance.emailTemplate.title') }}
      </h2>
      <el-button v-if="canSend" type="primary" @click="openCreate">
        <AppIcon iconName="app-add-outlined" class="mr-4" />
        {{ $t('views.finance.emailTemplate.actions.add') }}
      </el-button>
    </div>

    <p class="finance-email-template__hint mb-16">
      {{ $t('views.finance.emailTemplate.hint') }}
    </p>

    <el-table
      v-loading="loading"
      :data="list"
      empty-text=" "
      style="width: 100%"
    >
      <el-table-column
        prop="name"
        :label="$t('views.finance.emailTemplate.columns.name')"
        min-width="160"
      />
      <el-table-column
        prop="subject"
        :label="$t('views.finance.emailTemplate.columns.subject')"
        min-width="240"
        show-overflow-tooltip
      />
      <el-table-column
        :label="$t('views.finance.emailTemplate.columns.scenario')"
        width="140"
      >
        <template #default="{ row }">
          {{ $t(`views.finance.emailTemplate.scenario.${row.scenario}`) }}
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.emailTemplate.columns.isActive')"
        width="100"
      >
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active
              ? $t('views.finance.emailTemplate.columns.active')
              : $t('views.finance.emailTemplate.columns.inactive') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.emailTemplate.columns.actions')"
        width="180"
      >
        <template #default="{ row }">
          <el-button
            v-if="canSend"
            link
            type="primary"
            @click="openEdit(row)"
          >
            {{ $t('views.finance.emailTemplate.actions.edit') }}
          </el-button>
          <el-button
            v-if="canSend"
            link
            type="danger"
            @click="confirmDelete(row)"
          >
            {{ $t('views.finance.emailTemplate.actions.delete') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="list.length === 0 && !loading" class="finance-email-template__empty">
      {{ $t('views.finance.emailTemplate.empty') }}
    </div>

    <!-- Create / Edit dialog -->
    <el-dialog
      v-model="formVisible"
      :title="editMode
        ? $t('views.finance.emailTemplate.dialog.editTitle')
        : $t('views.finance.emailTemplate.dialog.createTitle')"
      width="720px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
      >
        <div class="flex" style="gap: 12px">
          <el-form-item
            :label="$t('views.finance.emailTemplate.form.name')"
            prop="name"
            style="flex: 1"
          >
            <el-input v-model="form.name" maxlength="100" />
          </el-form-item>
          <el-form-item
            :label="$t('views.finance.emailTemplate.form.scenario')"
            prop="scenario"
            style="width: 220px"
          >
            <el-select v-model="form.scenario" style="width: 100%">
              <el-option
                v-for="opt in scenarioOptions"
                :key="opt"
                :value="opt"
                :label="$t(`views.finance.emailTemplate.scenario.${opt}`)"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item
          :label="$t('views.finance.emailTemplate.form.subject')"
          prop="subject"
        >
          <el-input v-model="form.subject" maxlength="255" />
        </el-form-item>
        <el-form-item
          :label="$t('views.finance.emailTemplate.form.bodyText')"
          prop="body_text"
        >
          <el-input
            v-model="form.body_text"
            type="textarea"
            :rows="8"
          />
        </el-form-item>
        <el-form-item :label="$t('views.finance.emailTemplate.form.bodyHtml')">
          <el-input
            v-model="form.body_html"
            type="textarea"
            :rows="6"
            :placeholder="$t('views.finance.emailTemplate.form.bodyHtmlPlaceholder')"
          />
        </el-form-item>
        <p class="finance-email-template__placeholders">
          {{ $t('views.finance.emailTemplate.form.placeholderHint') }}
        </p>
        <el-form-item>
          <el-checkbox v-model="form.is_active">
            {{ $t('views.finance.emailTemplate.form.isActive') }}
          </el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="primary" :loading="saving" @click="onSubmit">
          {{ $t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { MsgConfirm, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import {
  createEmailTemplate,
  deleteEmailTemplate,
  listEmailTemplates,
  updateEmailTemplate,
} from '@/api/finance/email-template'
import type {
  EmailTemplate,
  EmailTemplateCreate,
  EmailTemplateScenario,
  EmailTemplateUpdate,
} from '@/api/finance/type'

const { user } = useStore()

const list = ref<EmailTemplate[]>([])
const loading = ref(false)
const saving = ref(false)

const formVisible = ref(false)
const editMode = ref(false)
const editingId = ref<string>('')
const formRef = ref<FormInstance>()

const scenarioOptions: EmailTemplateScenario[] = [
  'materials',
  'progress_report',
  'general',
  'other',
]

const initialForm: EmailTemplateCreate = {
  name: '',
  subject: '',
  body_text: '',
  body_html: '',
  scenario: 'materials',
  is_active: true,
}
const form = reactive<EmailTemplateCreate>({ ...initialForm })

const canSend = computed(() =>
  hasPermission(
    [
      RoleConst.ADMIN,
      RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
      PermissionConst.FINANCE_SEND.getWorkspacePermission,
      PermissionConst.FINANCE_SEND.getWorkspacePermissionWorkspaceManageRole,
    ],
    'OR',
  ),
)

const rules = computed<FormRules>(() => ({
  name: [
    {
      required: true,
      message: t('views.finance.emailTemplate.validation.nameRequired'),
      trigger: 'blur',
    },
  ],
  subject: [
    {
      required: true,
      message: t('views.finance.emailTemplate.validation.subjectRequired'),
      trigger: 'blur',
    },
  ],
  body_text: [
    {
      required: true,
      message: t('views.finance.emailTemplate.validation.bodyRequired'),
      trigger: 'blur',
    },
  ],
}))

const fetchList = async () => {
  const wid = user.getWorkspaceId()
  if (!wid) return
  loading.value = true
  try {
    const res = await listEmailTemplates(wid, { size: 100 })
    list.value = (res.data?.records as EmailTemplate[]) || []
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  Object.assign(form, initialForm)
}

const openCreate = () => {
  resetForm()
  editMode.value = false
  editingId.value = ''
  formVisible.value = true
}

const openEdit = (row: EmailTemplate) => {
  Object.assign(form, {
    name: row.name,
    subject: row.subject,
    body_text: row.body_text,
    body_html: row.body_html,
    scenario: row.scenario,
    is_active: row.is_active,
  })
  editMode.value = true
  editingId.value = row.id
  formVisible.value = true
}

const onSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    const wid = user.getWorkspaceId()
    if (!wid) return
    saving.value = true
    try {
      if (editMode.value) {
        const body: EmailTemplateUpdate = { ...form }
        await updateEmailTemplate(wid, editingId.value, body)
      } else {
        await createEmailTemplate(wid, { ...form })
      }
      MsgSuccess(t('common.saveSuccess'))
      formVisible.value = false
      await fetchList()
    } finally {
      saving.value = false
    }
  })
}

const confirmDelete = async (row: EmailTemplate) => {
  try {
    await MsgConfirm(
      t('views.finance.emailTemplate.dialog.deleteTitle'),
      t('views.finance.emailTemplate.dialog.deleteConfirm', { name: row.name }),
    )
  } catch {
    return
  }
  const wid = user.getWorkspaceId()
  if (!wid) return
  await deleteEmailTemplate(wid, row.id)
  MsgSuccess(t('common.deleteSuccess'))
  await fetchList()
}

onMounted(() => {
  fetchList()
})
</script>

<style lang="scss" scoped>
.finance-email-template {
  &__title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
  &__hint,
  &__placeholders {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
  &__placeholders {
    margin: -8px 0 12px;
    background: var(--el-fill-color-light);
    padding: 8px 12px;
    border-radius: 4px;
  }
  &__empty {
    color: var(--el-text-color-secondary);
    text-align: center;
    padding: 32px;
  }
}
</style>

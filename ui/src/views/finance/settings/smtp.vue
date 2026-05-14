<template>
  <div class="finance-smtp p-24">
    <div class="finance-smtp__header flex-between mb-16">
      <h2 class="finance-smtp__title">{{ $t('views.finance.smtp.title') }}</h2>
      <el-button v-if="canSend" type="primary" @click="openCreate">
        <AppIcon iconName="app-add-outlined" class="mr-4" />
        {{ $t('views.finance.smtp.actions.add') }}
      </el-button>
    </div>

    <p class="finance-smtp__hint mb-16">
      {{ $t('views.finance.smtp.hint') }}
    </p>

    <el-table
      v-loading="loading"
      :data="list"
      empty-text=" "
      style="width: 100%"
    >
      <el-table-column
        prop="name"
        :label="$t('views.finance.smtp.columns.name')"
        min-width="160"
      />
      <el-table-column
        :label="$t('views.finance.smtp.columns.host')"
        min-width="240"
      >
        <template #default="{ row }">
          <span>{{ row.host }}:{{ row.port }}</span>
          <el-tag
            v-if="row.use_ssl"
            size="small"
            type="success"
            class="ml-4"
          >SSL</el-tag>
          <el-tag
            v-else-if="row.use_tls"
            size="small"
            type="info"
            class="ml-4"
          >TLS</el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="from_email"
        :label="$t('views.finance.smtp.columns.fromEmail')"
        min-width="200"
      />
      <el-table-column
        :label="$t('views.finance.smtp.columns.isDefault')"
        width="100"
      >
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="success" size="small">
            {{ $t('views.finance.smtp.columns.default') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('views.finance.smtp.columns.actions')"
        width="240"
      >
        <template #default="{ row }">
          <el-button
            v-if="canSend"
            link
            type="primary"
            @click="openTest(row)"
          >
            {{ $t('views.finance.smtp.actions.test') }}
          </el-button>
          <el-button
            v-if="canSend"
            link
            type="primary"
            @click="openEdit(row)"
          >
            {{ $t('views.finance.smtp.actions.edit') }}
          </el-button>
          <el-button
            v-if="canSend"
            link
            type="danger"
            @click="confirmDelete(row)"
          >
            {{ $t('views.finance.smtp.actions.delete') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="list.length === 0 && !loading" class="finance-smtp__empty">
      {{ $t('views.finance.smtp.empty') }}
    </div>

    <!-- Create / Edit dialog -->
    <el-dialog
      v-model="formVisible"
      :title="editMode
        ? $t('views.finance.smtp.dialog.editTitle')
        : $t('views.finance.smtp.dialog.createTitle')"
      width="640px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
      >
        <el-form-item
          :label="$t('views.finance.smtp.form.name')"
          prop="name"
        >
          <el-input v-model="form.name" maxlength="100" />
        </el-form-item>
        <div class="flex" style="gap: 12px">
          <el-form-item
            :label="$t('views.finance.smtp.form.host')"
            prop="host"
            style="flex: 1"
          >
            <el-input v-model="form.host" />
          </el-form-item>
          <el-form-item
            :label="$t('views.finance.smtp.form.port')"
            prop="port"
            style="width: 140px"
          >
            <el-input-number
              v-model="form.port"
              :min="1"
              :max="65535"
              :controls="false"
              style="width: 100%"
            />
          </el-form-item>
        </div>
        <div class="flex" style="gap: 12px">
          <el-form-item
            :label="$t('views.finance.smtp.form.fromEmail')"
            prop="from_email"
            style="flex: 1"
          >
            <el-input v-model="form.from_email" />
          </el-form-item>
          <el-form-item
            :label="$t('views.finance.smtp.form.fromName')"
            prop="from_name"
            style="flex: 1"
          >
            <el-input v-model="form.from_name" maxlength="100" />
          </el-form-item>
        </div>
        <el-form-item
          :label="$t('views.finance.smtp.form.username')"
          prop="username"
        >
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item
          :label="$t('views.finance.smtp.form.password')"
          prop="password"
        >
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="editMode
              ? $t('views.finance.smtp.form.passwordKeepHint')
              : $t('views.finance.smtp.form.passwordPlaceholder')"
          />
        </el-form-item>
        <div class="flex" style="gap: 24px">
          <el-form-item>
            <el-checkbox v-model="form.use_tls">
              {{ $t('views.finance.smtp.form.useTls') }}
            </el-checkbox>
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.use_ssl">
              {{ $t('views.finance.smtp.form.useSsl') }}
            </el-checkbox>
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.is_default">
              {{ $t('views.finance.smtp.form.isDefault') }}
            </el-checkbox>
          </el-form-item>
        </div>
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

    <!-- Test dialog -->
    <el-dialog
      v-model="testVisible"
      :title="$t('views.finance.smtp.dialog.testTitle')"
      width="420px"
    >
      <el-form label-position="top">
        <el-form-item :label="$t('views.finance.smtp.form.testTo')">
          <el-input
            v-model="testForm.to_address"
            placeholder="recipient@example.com"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testVisible = false">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="primary" :loading="testing" @click="onTest">
          {{ $t('views.finance.smtp.actions.test') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { MsgConfirm, MsgError, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import {
  createSmtpConfig,
  deleteSmtpConfig,
  listSmtpConfigs,
  testSmtpConfig,
  updateSmtpConfig,
} from '@/api/finance/smtp-config'
import type {
  SmtpConfig,
  SmtpConfigCreate,
  SmtpConfigUpdate,
} from '@/api/finance/type'

const { user } = useStore()

const list = ref<SmtpConfig[]>([])
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)

const formVisible = ref(false)
const editMode = ref(false)
const editingId = ref<string>('')
const formRef = ref<FormInstance>()
const initialForm: SmtpConfigCreate = {
  name: '',
  host: '',
  port: 587,
  username: '',
  password: '',
  from_email: '',
  from_name: '',
  use_tls: true,
  use_ssl: false,
  is_default: false,
}
const form = reactive<SmtpConfigCreate>({ ...initialForm })

const testVisible = ref(false)
const testTargetId = ref<string>('')
const testForm = reactive({ to_address: '' })

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
  name: [{ required: true, message: t('views.finance.smtp.validation.nameRequired'), trigger: 'blur' }],
  host: [{ required: true, message: t('views.finance.smtp.validation.hostRequired'), trigger: 'blur' }],
  port: [{ required: true, message: t('views.finance.smtp.validation.portRequired'), trigger: 'blur' }],
  username: [{ required: true, message: t('views.finance.smtp.validation.usernameRequired'), trigger: 'blur' }],
  password: editMode.value
    ? []
    : [
        {
          required: true,
          message: t('views.finance.smtp.validation.passwordRequired'),
          trigger: 'blur',
        },
      ],
  from_email: [
    {
      required: true,
      type: 'email',
      message: t('views.finance.smtp.validation.fromEmailInvalid'),
      trigger: 'blur',
    },
  ],
}))

const fetchList = async () => {
  const wid = user.getWorkspaceId()
  if (!wid) return
  loading.value = true
  try {
    const res = await listSmtpConfigs(wid, { size: 100 })
    // PageResult shape: {records, total, current, size}.
    list.value = (res.data?.records as SmtpConfig[]) || []
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

const openEdit = (row: SmtpConfig) => {
  Object.assign(form, {
    name: row.name,
    host: row.host,
    port: row.port,
    username: row.username,
    password: '',
    from_email: row.from_email,
    from_name: row.from_name,
    use_tls: row.use_tls,
    use_ssl: row.use_ssl,
    is_default: row.is_default,
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
        const body: SmtpConfigUpdate = {
          name: form.name,
          host: form.host,
          port: form.port,
          username: form.username,
          from_email: form.from_email,
          from_name: form.from_name,
          use_tls: form.use_tls,
          use_ssl: form.use_ssl,
          is_default: form.is_default,
        }
        if (form.password) body.password = form.password
        await updateSmtpConfig(wid, editingId.value, body)
      } else {
        await createSmtpConfig(wid, { ...form })
      }
      MsgSuccess(t('common.saveSuccess'))
      formVisible.value = false
      await fetchList()
    } finally {
      saving.value = false
    }
  })
}

const confirmDelete = async (row: SmtpConfig) => {
  try {
    await MsgConfirm(
      t('views.finance.smtp.dialog.deleteTitle'),
      t('views.finance.smtp.dialog.deleteConfirm', { name: row.name }),
    )
  } catch {
    return
  }
  const wid = user.getWorkspaceId()
  if (!wid) return
  await deleteSmtpConfig(wid, row.id)
  MsgSuccess(t('common.deleteSuccess'))
  await fetchList()
}

const openTest = (row: SmtpConfig) => {
  testTargetId.value = row.id
  testForm.to_address = ''
  testVisible.value = true
}

const onTest = async () => {
  if (!testForm.to_address) {
    MsgError(t('views.finance.smtp.validation.testToRequired'))
    return
  }
  const wid = user.getWorkspaceId()
  if (!wid) return
  testing.value = true
  try {
    const res = await testSmtpConfig(wid, testTargetId.value, {
      to_address: testForm.to_address,
    })
    if (res.data?.success) {
      MsgSuccess(t('views.finance.smtp.testSuccess'))
      testVisible.value = false
    } else {
      MsgError(
        t('views.finance.smtp.testFailed') +
          (res.data?.error ? `: ${res.data.error}` : ''),
      )
    }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  fetchList()
})
</script>

<style lang="scss" scoped>
.finance-smtp {
  &__title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
  &__hint {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
  &__empty {
    color: var(--el-text-color-secondary);
    text-align: center;
    padding: 32px;
  }
}
</style>

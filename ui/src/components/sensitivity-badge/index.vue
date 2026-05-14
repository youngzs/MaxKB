<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { EditPen } from '@element-plus/icons-vue'
import { MsgError, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { hasPermission } from '@/utils/permission'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import { updateDocumentSensitivity } from '@/api/finance/document-sensitivity'

type SensitivityValue =
  | 'public'
  | 'internal'
  | 'confidential'
  | 'secret'
  | string
  | null
  | undefined

const props = withDefaults(
  defineProps<{
    level?: SensitivityValue
    size?: 'small' | 'default' | 'large'
    /** When true, clicking the tag opens a popover with a select to update the
     *  document's sensitivity level. Requires `documentId` to be set. */
    editable?: boolean
    /** Knowledge document id — only used when `editable` is true. */
    documentId?: string
  }>(),
  {
    level: 'internal',
    size: 'small',
    editable: false,
    documentId: '',
  },
)

const emit = defineEmits<{
  /** Fires after a successful update with the new level. */
  (e: 'update', value: string): void
}>()

const { user } = useStore()

const LEVELS: ReadonlyArray<'public' | 'internal' | 'confidential' | 'secret'> = [
  'public',
  'internal',
  'confidential',
  'secret',
]

const typeMap: Record<string, 'info' | '' | 'warning' | 'danger'> = {
  public: 'info',
  internal: '',
  confidential: 'warning',
  secret: 'danger',
}

const normalizedLevel = computed(() => props.level || 'internal')
const tagType = computed(
  () => typeMap[normalizedLevel.value as keyof typeof typeMap] ?? '',
)

/** Permission gate — only finance template managers (or admins / workspace
 *  managers) may change the sensitivity tag. Non-managers see the popover
 *  in a disabled state with a tooltip-style hint. */
const canEdit = computed(() =>
  hasPermission(
    [
      RoleConst.ADMIN,
      RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
      PermissionConst.FINANCE_TEMPLATE_MANAGE.getWorkspacePermission,
      PermissionConst.FINANCE_TEMPLATE_MANAGE.getWorkspacePermissionWorkspaceManageRole,
    ],
    'OR',
  ),
)

const popoverVisible = ref(false)
const editing = ref<string>(normalizedLevel.value)
const saving = ref(false)
/** When true, the tag briefly fades to acknowledge a successful save. */
const fading = ref(false)

// Sync the working draft when the upstream level changes (e.g. row refresh).
watch(
  () => props.level,
  (v) => {
    editing.value = (v || 'internal') as string
  },
)

const onOpen = () => {
  editing.value = normalizedLevel.value
}

const onSave = async () => {
  if (!props.documentId) {
    MsgError(t('common.sensitivity.editMissingDoc'))
    return
  }
  if (editing.value === normalizedLevel.value) {
    popoverVisible.value = false
    return
  }
  const wid = user.getWorkspaceId()
  if (!wid) return
  saving.value = true
  try {
    await updateDocumentSensitivity(wid, props.documentId, {
      sensitivity_level: editing.value as
        | 'public'
        | 'internal'
        | 'confidential'
        | 'secret',
    })
    emit('update', editing.value)
    MsgSuccess(t('common.sensitivity.editSuccess'))
    popoverVisible.value = false
    fading.value = true
    setTimeout(() => {
      fading.value = false
    }, 800)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-popover
    v-if="editable"
    v-model:visible="popoverVisible"
    :width="280"
    trigger="click"
    placement="bottom-start"
    :disabled="!canEdit"
    @show="onOpen"
  >
    <template #reference>
      <el-tooltip
        v-if="!canEdit"
        :content="$t('common.sensitivity.editPermissionDenied')"
        placement="top"
      >
        <el-tag
          :type="tagType"
          :size="size"
          effect="plain"
          class="finance-sensitivity-badge"
          :class="{ 'finance-sensitivity-badge--fade': fading }"
        >
          {{ $t(`common.sensitivity.${normalizedLevel}`) }}
        </el-tag>
      </el-tooltip>
      <el-tag
        v-else
        :type="tagType"
        :size="size"
        effect="plain"
        class="finance-sensitivity-badge finance-sensitivity-badge--editable"
        :class="{ 'finance-sensitivity-badge--fade': fading }"
      >
        {{ $t(`common.sensitivity.${normalizedLevel}`) }}
        <el-icon class="finance-sensitivity-badge__icon">
          <EditPen />
        </el-icon>
      </el-tag>
    </template>
    <div class="finance-sensitivity-badge__panel">
      <div class="finance-sensitivity-badge__panel-title">
        {{ $t('common.sensitivity.edit') }}
      </div>
      <el-select
        v-model="editing"
        size="small"
        style="width: 100%"
        :disabled="saving"
      >
        <el-option
          v-for="lvl in LEVELS"
          :key="lvl"
          :value="lvl"
          :label="$t(`common.sensitivity.${lvl}`)"
        />
      </el-select>
      <div class="finance-sensitivity-badge__panel-actions">
        <el-button
          size="small"
          :disabled="saving"
          @click="popoverVisible = false"
        >
          {{ $t('common.cancel') }}
        </el-button>
        <el-button
          size="small"
          type="primary"
          :loading="saving"
          @click="onSave"
        >
          {{ $t('common.sensitivity.editSave') }}
        </el-button>
      </div>
    </div>
  </el-popover>

  <el-tag
    v-else
    :type="tagType"
    :size="size"
    effect="plain"
  >
    {{ $t(`common.sensitivity.${normalizedLevel}`) }}
  </el-tag>
</template>

<style lang="scss" scoped>
.finance-sensitivity-badge {
  transition: opacity 0.6s ease, box-shadow 0.6s ease;

  &--editable {
    cursor: pointer;
  }

  &--fade {
    opacity: 0.4;
  }

  &__icon {
    margin-left: 4px;
    font-size: 11px;
    vertical-align: middle;
  }

  &__panel-title {
    font-size: 13px;
    color: var(--el-text-color-regular);
    margin-bottom: 8px;
  }

  &__panel-actions {
    margin-top: 12px;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
}
</style>

<template>
  <el-dialog
    v-model="visible"
    :title="$t('views.finance.materials.detail.editDialog.title')"
    width="780px"
    append-to-body
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @closed="reset"
  >
    <el-alert type="info" :closable="false" show-icon class="mb-12">
      <template #title>
        <span>{{ $t('views.finance.materials.detail.editDialog.alert') }}</span>
      </template>
    </el-alert>

    <el-form
      label-position="top"
      require-asterisk-position="right"
      @submit.prevent
    >
      <el-form-item :label="$t('views.finance.materials.detail.editDialog.requirementTextLabel')">
        <el-input
          v-model="requirementText"
          type="textarea"
          :rows="3"
          maxlength="20000"
          :placeholder="$t('views.finance.materials.detail.editDialog.requirementTextPlaceholder')"
          show-word-limit
        />
      </el-form-item>

      <el-form-item>
        <template #label>
          <div class="finance-mat-edit__header">
            <span>{{ $t('views.finance.materials.detail.editDialog.itemsHeader', { n: items.length }) }}</span>
            <el-button
              type="primary"
              size="small"
              plain
              @click="addItem"
            >
              <AppIcon iconName="app-add" class="mr-4" />
              {{ $t('views.finance.materials.detail.editDialog.addRow') }}
            </el-button>
          </div>
        </template>

        <el-table
          v-if="items.length > 0"
          :data="items"
          stripe
          row-key="key"
          style="width: 100%"
        >
          <el-table-column :label="$t('views.finance.materials.detail.editDialog.keyColumn')" min-width="160">
            <template #default="{ row, $index }">
              <el-input
                v-model="row.key"
                size="small"
                :placeholder="$t('views.finance.materials.detail.editDialog.keyPlaceholder')"
                @blur="onKeyBlur($index)"
              />
            </template>
          </el-table-column>
          <el-table-column :label="$t('views.finance.materials.detail.editDialog.labelColumn')" min-width="180">
            <template #default="{ row }">
              <el-input
                v-model="row.label"
                size="small"
                :placeholder="$t('views.finance.materials.detail.editDialog.labelPlaceholder')"
                maxlength="200"
              />
            </template>
          </el-table-column>
          <el-table-column :label="$t('views.finance.materials.detail.editDialog.descColumn')" min-width="220">
            <template #default="{ row }">
              <el-input
                v-model="row.description"
                size="small"
                :placeholder="$t('views.finance.materials.detail.editDialog.descPlaceholder')"
                maxlength="2000"
              />
            </template>
          </el-table-column>
          <el-table-column :label="$t('views.finance.materials.detail.editDialog.requiredColumn')" width="76" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.required" />
            </template>
          </el-table-column>
          <el-table-column label="" width="56" align="center" fixed="right">
            <template #default="{ $index }">
              <el-button
                link
                type="danger"
                size="small"
                @click="removeItem($index)"
              >
                <AppIcon iconName="app-delete" />
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-else class="finance-mat-edit__empty">
          {{ $t('views.finance.materials.detail.editDialog.empty') }}
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button :disabled="saving" @click="visible = false">
          {{ $t('views.finance.materials.detail.editDialog.cancel') }}
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="!isValid"
          @click="onSave"
        >
          {{ $t('views.finance.materials.detail.editDialog.save') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { MsgError, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import type { MaterialsTask, ParsedItem } from '@/api/finance/type'

interface Props {
  modelValue: boolean
  task: MaterialsTask | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', updated: MaterialsTask): void
}>()

const { user, financeMaterials } = useStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const requirementText = ref('')
// EditableItem: parsed_items 的本地编辑副本。`required` 不可为 undefined 因为
// el-switch 默认 false 时是有意义的"非必备"，与 undefined 不同 —— 保存前
// 我们会显式 fallback 为 true（同后端 schema 默认值）。
interface EditableItem {
  key: string
  label: string
  description: string
  required: boolean
}
const items = ref<EditableItem[]>([])
const saving = ref(false)

const isValid = computed(() => {
  for (const it of items.value) {
    if (!it.key.trim()) return false
    if (!it.label.trim()) return false
    // 检查 key 唯一性
    const dup = items.value.filter((x) => x.key.trim() === it.key.trim()).length
    if (dup > 1) return false
  }
  return true
})

// Reset & rehydrate whenever the dialog opens with a fresh task payload.
watch(
  () => [props.modelValue, props.task?.id],
  ([open]) => {
    if (open && props.task) {
      requirementText.value = props.task.requirement_text || ''
      items.value = (props.task.parsed_items || []).map((it: ParsedItem) => ({
        key: String(it.key ?? '').trim(),
        label: String(it.label ?? '').trim(),
        description: String(it.description ?? '').trim(),
        required: it.required !== false, // default true to match backend
      }))
    }
  },
)

function reset() {
  // 关闭后让 dialog 内部状态自然丢弃；下次打开会通过 watch 重新填。
  items.value = []
  requirementText.value = ''
}

function addItem() {
  // 默认 key 用 item_N，用户必须改成有意义的 snake_case；schema 仅要求非空。
  const nextIndex = items.value.length + 1
  items.value.push({
    key: `item_${nextIndex}`,
    label: '',
    description: '',
    required: true,
  })
}

function removeItem(idx: number) {
  items.value.splice(idx, 1)
}

function onKeyBlur(idx: number) {
  // 自动 snake_case：把空格 → 下划线，转小写。仅触发 blur，避免输入中干扰。
  const v = items.value[idx]
  if (!v) return
  v.key = v.key.trim().replace(/\s+/g, '_').toLowerCase()
}

async function onSave() {
  if (!props.task || !isValid.value) {
    MsgError(t('views.finance.materials.detail.editDialog.invalidMessage'))
    return
  }
  const workspaceId = user.getWorkspaceId()
  if (!workspaceId) return
  saving.value = true
  try {
    const body = {
      requirement_text: requirementText.value,
      parsed_items: items.value.map((it) => ({
        key: it.key.trim(),
        label: it.label.trim(),
        description: it.description.trim() || '',
        required: it.required,
      })),
    }
    const updated = await financeMaterials.update(workspaceId, props.task.id, body)
    if (updated) {
      MsgSuccess(t('views.finance.materials.detail.editDialog.saveSuccess'))
      emit('success', updated)
      visible.value = false
    }
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.finance-mat-edit__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.finance-mat-edit__empty {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 24px 0;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 13px;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>

<template>
  <NodeContainer :nodeModel="nodeModel">
    <h5 class="title-decoration-1 mb-8">{{ $t('workflow.nodeSetting') }}</h5>
    <el-card shadow="never" class="card-never">
      <el-form
        ref="formRef"
        @submit.prevent
        :model="form_data"
        label-position="top"
        require-asterisk-position="right"
        label-width="auto"
      >
        <el-form-item
          :label="$t('workflow.nodes.zipPack.documentKeys')"
          prop="document_oss_keys_text"
          :rules="{
            validator: validateKeys,
            trigger: 'blur',
          }"
        >
          <el-input
            v-model="form_data.document_oss_keys_text"
            type="textarea"
            :rows="4"
            :placeholder="$t('workflow.nodes.zipPack.documentKeysPlaceholder')"
          />
        </el-form-item>
        <el-form-item
          :label="$t('workflow.nodes.zipPack.documentNames')"
          prop="document_names_text"
          :rules="{
            validator: validateNames,
            trigger: 'blur',
          }"
        >
          <el-input
            v-model="form_data.document_names_text"
            type="textarea"
            :rows="3"
            :placeholder="$t('workflow.nodes.zipPack.documentNamesPlaceholder')"
          />
        </el-form-item>
        <el-form-item
          :label="$t('workflow.nodes.zipPack.itemFolders')"
          prop="item_folders_text"
          :rules="{
            validator: validateFolders,
            trigger: 'blur',
          }"
        >
          <el-input
            v-model="form_data.item_folders_text"
            type="textarea"
            :rows="3"
            :placeholder="$t('workflow.nodes.zipPack.itemFoldersPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="$t('workflow.nodes.zipPack.archiveName')">
          <el-input
            v-model="form_data.archive_name"
            :placeholder="$t('workflow.nodes.zipPack.archiveNamePlaceholder')"
          />
        </el-form-item>
      </el-form>
    </el-card>
  </NodeContainer>
</template>

<script setup lang="ts">
import NodeContainer from '@/workflow/common/NodeContainer.vue'
import { computed, ref, onMounted } from 'vue'
import { set } from 'lodash'
import { t } from '@/locales'

const props = defineProps<{ nodeModel: any }>()

const form = {
  // The form keeps the three list-typed inputs as textareas; the validators
  // below parse them (one entry per non-empty line) and write the resulting
  // arrays to the *_oss_keys / *_names / *_folders props that ship to the
  // backend serializer.
  document_oss_keys_text: '',
  document_oss_keys: [] as string[],
  document_names_text: '',
  document_names: [] as string[],
  item_folders_text: '',
  item_folders: [] as string[],
  archive_name: 'materials.zip',
}

const form_data = computed({
  get: () => {
    if (props.nodeModel.properties.node_data) {
      return props.nodeModel.properties.node_data
    } else {
      set(props.nodeModel.properties, 'node_data', form)
    }
    return props.nodeModel.properties.node_data
  },
  set: (value) => {
    set(props.nodeModel.properties, 'node_data', value)
  },
})

const _parseLines = (raw: string): string[] => {
  if (!raw) return []
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

const validateKeys = (_rule: any, value: string, callback: (err?: Error) => void) => {
  const arr = _parseLines(value)
  if (arr.length === 0) {
    callback(new Error(t('workflow.nodes.zipPack.documentKeysRequired')))
    return
  }
  set(props.nodeModel.properties.node_data, 'document_oss_keys', arr)
  callback()
}

const validateNames = (_rule: any, value: string, callback: (err?: Error) => void) => {
  const arr = _parseLines(value)
  set(props.nodeModel.properties.node_data, 'document_names', arr)
  callback()
}

const validateFolders = (_rule: any, value: string, callback: (err?: Error) => void) => {
  const arr = _parseLines(value)
  set(props.nodeModel.properties.node_data, 'item_folders', arr)
  callback()
}

const formRef = ref<any>()
const validate = () => {
  return new Promise<void>((resolve, reject) => {
    if (!formRef.value) {
      resolve()
      return
    }
    formRef.value.validate((valid: boolean, fields: any) => {
      if (valid) {
        resolve()
      } else {
        reject({ node: props.nodeModel, errMessage: fields })
      }
    })
  })
}

onMounted(() => {
  set(props.nodeModel, 'validate', validate)
})
</script>

<style lang="scss" scoped></style>

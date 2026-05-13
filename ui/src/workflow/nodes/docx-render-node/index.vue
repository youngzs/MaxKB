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
          :label="$t('workflow.nodes.docxRender.templateKey')"
          prop="template_oss_key"
          :rules="{
            required: true,
            message: $t('workflow.nodes.docxRender.templateKeyPlaceholder'),
            trigger: 'blur',
          }"
        >
          <el-input
            v-model="form_data.template_oss_key"
            :placeholder="$t('workflow.nodes.docxRender.templateKeyPlaceholder')"
            clearable
          />
        </el-form-item>
        <el-form-item
          :label="$t('workflow.nodes.docxRender.values')"
          prop="placeholder_values_text"
          :rules="{
            validator: validateJson,
            trigger: 'blur',
          }"
        >
          <el-input
            v-model="form_data.placeholder_values_text"
            type="textarea"
            :rows="6"
            :placeholder="$t('workflow.nodes.docxRender.valuesPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="$t('workflow.nodes.docxRender.outputFilename')">
          <el-input
            v-model="form_data.output_filename"
            :placeholder="$t('workflow.nodes.docxRender.outputFilenamePlaceholder')"
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
  template_oss_key: '',
  // The form keeps a JSON string for the user to edit; on save the parsed
  // object is also written to placeholder_values so backend serializer
  // receives a real dict. Form validator below enforces parseability.
  placeholder_values_text: '{}',
  placeholder_values: {},
  output_filename: 'output.docx',
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

const validateJson = (_rule: any, value: string, callback: (err?: Error) => void) => {
  if (value === undefined || value === null || value === '') {
    callback()
    return
  }
  try {
    const parsed = JSON.parse(value)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      callback(new Error(t('workflow.nodes.docxRender.valuesInvalid')))
      return
    }
    // Mirror the parsed object into placeholder_values so it ships to backend.
    set(props.nodeModel.properties.node_data, 'placeholder_values', parsed)
    callback()
  } catch (e) {
    callback(new Error(t('workflow.nodes.docxRender.valuesInvalid')))
  }
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

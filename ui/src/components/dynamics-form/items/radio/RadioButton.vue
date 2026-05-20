<template>
  <!--
    Element Plus 3.0：`label` 作为 value 已废弃，改用显式 `value`。slot 仍是
    显示文本（含 v-html 渲染的 label 函数返回值）。
  -->
  <el-radio-group v-bind="$attrs">
    <el-radio-button v-for="(item, index) in option_list" :key="index" :value="item[valueField]">
      <div v-html="label(item)"></div>
    </el-radio-button>
  </el-radio-group>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { FormField } from '@/components/dynamics-form/type'
import _ from 'lodash'

const props = defineProps<{
  formValue?: any
  formfieldList?: Array<FormField>
  field: string
  otherParams: any
  formField: FormField
  view?: boolean
}>()

const textField = computed(() => {
  return props.formField.text_field ? props.formField.text_field : 'key'
})

const valueField = computed(() => {
  return props.formField.value_field ? props.formField.value_field : 'value'
})

const option_list = computed(() => {
  return props.formField.option_list ? props.formField.option_list : []
})

const label = (option: any) => {
  return option[textField.value]
}
</script>
<style lang="scss"></style>

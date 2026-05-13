<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    level?: 'public' | 'internal' | 'confidential' | 'secret' | string | null
    size?: 'small' | 'default' | 'large'
  }>(),
  {
    level: 'internal',
    size: 'small',
  },
)

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
</script>

<template>
  <el-tag :type="tagType" :size="size" effect="plain">
    {{ $t(`common.sensitivity.${normalizedLevel}`) }}
  </el-tag>
</template>

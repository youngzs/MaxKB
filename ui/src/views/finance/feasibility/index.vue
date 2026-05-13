<template>
  <div class="finance-stub">
    <div class="finance-stub__inner">
      <el-tag class="finance-stub__badge" type="warning" effect="plain">
        P2 · {{ $t('views.finance.planning') }}
      </el-tag>
      <h2 class="finance-stub__title">{{ $t('views.finance.feasibility') }}</h2>
      <p class="finance-stub__subtitle">{{ $t('views.finance.comingSoon') }}</p>
      <el-button type="primary" text @click="goBack">
        {{ $t('views.finance.action.back') }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
function goBack() {
  router.push('/finance/overview')
}
</script>

<style lang="scss" scoped>
.finance-stub {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 200px);
  padding: 24px;

  &__inner {
    text-align: center;
  }

  &__badge {
    margin-bottom: 16px;
  }

  &__title {
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 12px;
    color: var(--el-text-color-primary);
  }

  &__subtitle {
    margin: 0 0 20px;
    color: var(--el-text-color-regular);
    font-size: 14px;
  }
}
</style>

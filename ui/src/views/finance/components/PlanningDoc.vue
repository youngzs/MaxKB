<template>
  <!--
    Shared "coming soon" rich-doc shell for P2 / P3 finance modules.
    Renders a phase badge, hero, capability sections, and an optional timeline.
    Use slots/props from each route so the doc can be tailored without forking.
  -->
  <div class="finance-planning">
    <div class="finance-planning__hero">
      <div class="finance-planning__meta">
        <el-tag
          class="finance-planning__phase"
          :type="phase === 'P3' ? 'info' : 'warning'"
          effect="plain"
        >
          {{ phase }} · {{ $t('views.finance.planning') }}
        </el-tag>
        <el-tag
          v-if="trackingId"
          class="finance-planning__tracking"
          type="info"
          effect="plain"
          size="small"
        >
          {{ trackingId }}
        </el-tag>
      </div>
      <h2 class="finance-planning__title">{{ title }}</h2>
      <p class="finance-planning__lead">{{ lead }}</p>
      <div class="finance-planning__actions">
        <el-button type="primary" @click="goBack">
          {{ $t('views.finance.action.back') }}
        </el-button>
        <el-button
          v-if="feedbackUrl"
          link
          type="primary"
          tag="a"
          :href="feedbackUrl"
          target="_blank"
          rel="noopener"
        >
          {{ $t('views.finance.planningDoc.feedback') }}
        </el-button>
      </div>
    </div>

    <el-card
      v-if="painPoints && painPoints.length"
      shadow="never"
      class="finance-planning__card"
    >
      <template #header>
        <strong>{{ $t('views.finance.planningDoc.painPoints') }}</strong>
      </template>
      <ul class="finance-planning__list">
        <li v-for="(it, idx) in painPoints" :key="idx">{{ it }}</li>
      </ul>
    </el-card>

    <el-card
      v-if="capabilities && capabilities.length"
      shadow="never"
      class="finance-planning__card"
    >
      <template #header>
        <strong>{{ $t('views.finance.planningDoc.capabilities') }}</strong>
      </template>
      <div class="finance-planning__caps">
        <div
          v-for="(cap, idx) in capabilities"
          :key="idx"
          class="finance-planning__cap"
        >
          <div class="finance-planning__cap-head">
            <span class="finance-planning__cap-icon">{{ cap.icon || '•' }}</span>
            <strong>{{ cap.title }}</strong>
          </div>
          <p class="finance-planning__cap-desc">{{ cap.desc }}</p>
        </div>
      </div>
    </el-card>

    <el-card
      v-if="flow && flow.length"
      shadow="never"
      class="finance-planning__card"
    >
      <template #header>
        <strong>{{ $t('views.finance.planningDoc.flow') }}</strong>
      </template>
      <el-steps :active="flow.length" align-center finish-status="success">
        <el-step
          v-for="(step, idx) in flow"
          :key="idx"
          :title="step.title"
          :description="step.desc"
        />
      </el-steps>
    </el-card>

    <el-card
      v-if="dependencies && dependencies.length"
      shadow="never"
      class="finance-planning__card"
    >
      <template #header>
        <strong>{{ $t('views.finance.planningDoc.dependencies') }}</strong>
      </template>
      <ul class="finance-planning__list">
        <li v-for="(it, idx) in dependencies" :key="idx">{{ it }}</li>
      </ul>
    </el-card>

    <el-card
      v-if="notDoing && notDoing.length"
      shadow="never"
      class="finance-planning__card finance-planning__card--muted"
    >
      <template #header>
        <strong>{{ $t('views.finance.planningDoc.notDoing') }}</strong>
      </template>
      <ul class="finance-planning__list">
        <li v-for="(it, idx) in notDoing" :key="idx">{{ it }}</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

interface Capability {
  icon?: string
  title: string
  desc: string
}

interface FlowStep {
  title: string
  desc?: string
}

withDefaults(
  defineProps<{
    phase: 'P2' | 'P3'
    title: string
    lead: string
    trackingId?: string
    feedbackUrl?: string
    painPoints?: string[]
    capabilities?: Capability[]
    flow?: FlowStep[]
    dependencies?: string[]
    notDoing?: string[]
  }>(),
  {
    trackingId: '',
    feedbackUrl: '',
    painPoints: () => [],
    capabilities: () => [],
    flow: () => [],
    dependencies: () => [],
    notDoing: () => [],
  },
)

const router = useRouter()
function goBack() {
  router.push('/finance/overview')
}
</script>

<style lang="scss" scoped>
.finance-planning {
  padding: 24px;
  max-width: 1080px;
  margin: 0 auto;

  &__hero {
    margin-bottom: 24px;
  }

  &__meta {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 16px;
  }

  &__title {
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 12px;
    color: var(--el-text-color-primary);
  }

  &__lead {
    margin: 0 0 16px;
    color: var(--el-text-color-regular);
    font-size: 14px;
    line-height: 1.65;
  }

  &__actions {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  &__card {
    margin-bottom: 16px;

    &--muted {
      background: var(--el-fill-color-lighter);
    }
  }

  &__list {
    margin: 0;
    padding-left: 20px;
    color: var(--el-text-color-regular);
    font-size: 14px;
    line-height: 1.8;
  }

  &__caps {
    display: grid;
    grid-template-columns: repeat(1, minmax(0, 1fr));
    gap: 16px;

    @media (min-width: 640px) {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  &__cap {
    padding: 12px 16px;
    border-radius: 6px;
    background: var(--el-fill-color-lighter);
  }

  &__cap-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    color: var(--el-text-color-primary);
  }

  &__cap-icon {
    font-size: 18px;
    line-height: 1;
  }

  &__cap-desc {
    margin: 0;
    color: var(--el-text-color-regular);
    font-size: 13px;
    line-height: 1.6;
  }
}
</style>

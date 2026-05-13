<template>
  <div class="finance-overview p-24">
    <div class="finance-overview__header mb-24">
      <h2 class="finance-overview__title">{{ $t('views.finance.overview') }}</h2>
      <p class="finance-overview__desc">{{ $t('views.finance.overviewDesc') }}</p>
    </div>

    <div class="finance-overview__grid">
      <el-card
        v-for="card in cards"
        :key="card.key"
        class="finance-overview__card"
        :class="{ 'is-disabled': card.disabled }"
        shadow="hover"
      >
        <div class="finance-overview__card-body">
          <div class="finance-overview__icon">{{ card.icon }}</div>
          <h3 class="finance-overview__card-title">
            {{ $t(card.titleKey) }}
          </h3>
          <p class="finance-overview__card-desc">{{ $t(card.descKey) }}</p>
          <div class="finance-overview__card-footer">
            <el-button
              v-if="!card.disabled"
              type="primary"
              text
              @click="goTo(card.path)"
            >
              {{ $t('views.finance.action.enter') }}
            </el-button>
            <el-tag v-else type="info" effect="plain">
              {{ $t('views.finance.planning') }}
            </el-tag>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

interface OverviewCard {
  key: string
  icon: string
  titleKey: string
  descKey: string
  path: string
  disabled?: boolean
}

const cards = computed<OverviewCard[]>(() => [
  {
    key: 'project',
    icon: '📂',
    titleKey: 'views.finance.cards.project.title',
    descKey: 'views.finance.cards.project.desc',
    path: '/finance/project',
  },
  {
    key: 'materials',
    icon: '📝',
    titleKey: 'views.finance.cards.materials.title',
    descKey: 'views.finance.cards.materials.desc',
    path: '/finance/materials',
  },
  {
    key: 'documents',
    icon: '📄',
    titleKey: 'views.finance.cards.documents.title',
    descKey: 'views.finance.cards.documents.desc',
    path: '/finance/documents',
  },
  {
    key: 'feasibility',
    icon: '🔍',
    titleKey: 'views.finance.cards.feasibility.title',
    descKey: 'views.finance.cards.feasibility.desc',
    path: '/finance/feasibility',
    disabled: true,
  },
  {
    key: 'progress',
    icon: '📈',
    titleKey: 'views.finance.cards.progress.title',
    descKey: 'views.finance.cards.progress.desc',
    path: '/finance/progress',
    disabled: true,
  },
])

function goTo(path: string) {
  router.push(path)
}
</script>

<style lang="scss" scoped>
.finance-overview {
  &__header {
    margin-bottom: 24px;
  }

  &__title {
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 8px;
    color: var(--el-text-color-primary);
  }

  &__desc {
    margin: 0;
    color: var(--el-text-color-regular);
    font-size: 14px;
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(1, minmax(0, 1fr));
    gap: 16px;

    @media (min-width: 640px) {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    @media (min-width: 1024px) {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
  }

  &__card {
    transition: transform 0.2s ease;

    &.is-disabled {
      opacity: 0.65;
      cursor: not-allowed;
    }
  }

  &__card-body {
    display: flex;
    flex-direction: column;
    min-height: 160px;
  }

  &__icon {
    font-size: 28px;
    line-height: 1;
    margin-bottom: 12px;
  }

  &__card-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 8px;
    color: var(--el-text-color-primary);
  }

  &__card-desc {
    flex: 1;
    margin: 0 0 16px;
    color: var(--el-text-color-regular);
    font-size: 13px;
    line-height: 1.5;
  }

  &__card-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
  }
}
</style>

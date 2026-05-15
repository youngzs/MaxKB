<template>
  <!--
    P2 · 进度归集 — "coming soon" rich-doc page.
    Source of truth: docs/finance-module-design.md §1.2 #4.
  -->
  <PlanningDoc
    phase="P2"
    tracking-id="FINANCE-PROGRESS"
    :title="$t('views.finance.progress')"
    :lead="$t('views.finance.planningDoc.progress.lead')"
    :pain-points="$tm('views.finance.planningDoc.progress.painPoints') as string[]"
    :capabilities="$tm('views.finance.planningDoc.progress.capabilities') as any"
    :flow="$tm('views.finance.planningDoc.progress.flow') as any"
    :dependencies="$tm('views.finance.planningDoc.progress.dependencies') as string[]"
    :not-doing="$tm('views.finance.planningDoc.progress.notDoing') as string[]"
  />
</template>

<script setup lang="ts">
import PlanningDoc from '../components/PlanningDoc.vue'
</script>

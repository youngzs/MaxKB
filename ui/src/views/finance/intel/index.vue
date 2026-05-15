<template>
  <!--
    P3 · 资讯推送 — "coming soon" rich-doc page.
    Source of truth: docs/finance-module-design.md §1.2 #1.
  -->
  <PlanningDoc
    phase="P3"
    tracking-id="FINANCE-INTEL"
    :title="$t('views.finance.intel')"
    :lead="$t('views.finance.planningDoc.intel.lead')"
    :pain-points="$tm('views.finance.planningDoc.intel.painPoints') as string[]"
    :capabilities="$tm('views.finance.planningDoc.intel.capabilities') as any"
    :flow="$tm('views.finance.planningDoc.intel.flow') as any"
    :dependencies="$tm('views.finance.planningDoc.intel.dependencies') as string[]"
    :not-doing="$tm('views.finance.planningDoc.intel.notDoing') as string[]"
  />
</template>

<script setup lang="ts">
import PlanningDoc from '../components/PlanningDoc.vue'
</script>

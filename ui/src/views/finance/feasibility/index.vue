<template>
  <!--
    P2 · 可行性初判 — "coming soon" rich-doc page.
    Renders the planned scope so users understand what they will get and why it
    isn't shipped yet. Source of truth: docs/finance-module-design.md §1.2 #2.
  -->
  <PlanningDoc
    phase="P2"
    tracking-id="FINANCE-FEASIBILITY"
    :title="$t('views.finance.feasibility')"
    :lead="$t('views.finance.planningDoc.feasibility.lead')"
    :pain-points="$tm('views.finance.planningDoc.feasibility.painPoints') as string[]"
    :capabilities="$tm('views.finance.planningDoc.feasibility.capabilities') as any"
    :flow="$tm('views.finance.planningDoc.feasibility.flow') as any"
    :dependencies="$tm('views.finance.planningDoc.feasibility.dependencies') as string[]"
    :not-doing="$tm('views.finance.planningDoc.feasibility.notDoing') as string[]"
  />
</template>

<script setup lang="ts">
import PlanningDoc from '../components/PlanningDoc.vue'
</script>

<script setup lang="ts">
defineProps<{ title?: string; description?: string }>();
</script>

<template>
  <div class="state-panel state-panel--empty">
    <span class="state-panel__zero" aria-hidden="true">0R</span>
    <h2>{{ title ?? $t("states.empty") }}</h2>
    <p v-if="description">{{ description }}</p>
    <slot />
  </div>
</template>

<script setup lang="ts">
defineProps<{ label?: string }>();
</script>

<template>
  <div class="state-panel" role="status">
    <span class="state-panel__loader" aria-hidden="true"></span>
    <p>{{ label ?? $t("states.loading") }}</p>
  </div>
</template>

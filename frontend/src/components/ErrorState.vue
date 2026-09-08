<script setup lang="ts">
defineProps<{ title?: string; description?: string }>();
defineEmits<{ retry: [] }>();
</script>

<template>
  <div class="state-panel state-panel--error" role="alert">
    <span class="state-panel__mark" aria-hidden="true">!</span>
    <h2>{{ title ?? $t("states.error") }}</h2>
    <p v-if="description">{{ description }}</p>
    <button
      class="button button--secondary"
      type="button"
      @click="$emit('retry')"
    >
      {{ $t("common.retry") }}
    </button>
  </div>
</template>

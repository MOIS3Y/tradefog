<script setup lang="ts">
import type { Component } from "vue";
defineProps<{
  title: string;
  description: string;
  icon: Component;
  embedded?: boolean;
}>();
</script>

<template>
  <header
    class="panel-heading"
    :class="{ 'panel-heading--embedded': embedded }"
  >
    <div>
      <h1><component :is="icon" :size="21" aria-hidden="true" />{{ title }}</h1>
      <p>{{ description }}</p>
    </div>
    <div v-if="$slots.default" class="panel-heading__actions"><slot /></div>
  </header>
</template>

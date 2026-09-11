<script setup lang="ts">
import { ref, watch } from "vue";
import { TooltipContent, TooltipRoot, TooltipTrigger } from "reka-ui";

const props = defineProps<{ label: string; disabled: boolean }>();
const open = ref(false);

watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) open.value = false;
  },
);
</script>

<template>
  <TooltipRoot v-model:open="open" :disabled="disabled">
    <TooltipTrigger as-child><slot /></TooltipTrigger>
    <TooltipContent class="sidebar-tooltip" side="right" :side-offset="12">
      {{ label }}
    </TooltipContent>
  </TooltipRoot>
</template>

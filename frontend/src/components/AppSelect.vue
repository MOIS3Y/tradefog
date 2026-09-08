<script setup lang="ts" generic="Value extends string">
import { Check, ChevronDown } from "@lucide/vue";
import {
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from "reka-ui";

export interface SelectOption<Value extends string = string> {
  value: Value;
  label: string;
}

defineProps<{
  modelValue: Value;
  options: SelectOption<Value>[];
  label: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: Value];
}>();

function updateValue(value: unknown): void {
  if (typeof value === "string") {
    emit("update:modelValue", value as Value);
  }
}
</script>

<template>
  <SelectRoot :model-value="modelValue" @update:model-value="updateValue">
    <SelectTrigger class="tf-select-trigger" :aria-label="label">
      <SelectValue />
      <SelectIcon class="tf-select-icon">
        <ChevronDown :size="15" aria-hidden="true" />
      </SelectIcon>
    </SelectTrigger>
    <SelectPortal to=".tf-app">
      <SelectContent
        class="tf-select-content"
        position="popper"
        :side-offset="6"
      >
        <SelectViewport class="tf-select-viewport">
          <SelectItem
            v-for="option in options"
            :key="option.value"
            class="tf-select-item"
            :value="option.value"
          >
            <SelectItemText>{{ option.label }}</SelectItemText>
            <SelectItemIndicator class="tf-select-indicator">
              <Check :size="14" aria-hidden="true" />
            </SelectItemIndicator>
          </SelectItem>
        </SelectViewport>
      </SelectContent>
    </SelectPortal>
  </SelectRoot>
</template>

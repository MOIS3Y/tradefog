<script setup lang="ts">
import { Check, ChevronDown } from "@lucide/vue";
import {
  ComboboxAnchor,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxItemIndicator,
  ComboboxPortal,
  ComboboxRoot,
  ComboboxTrigger,
  ComboboxViewport,
} from "reka-ui";

export interface SearchableOption {
  value: number;
  label: string;
  detail?: string;
}

const props = defineProps<{
  modelValue: number | null;
  options: SearchableOption[];
  placeholder: string;
  emptyLabel: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: number | null];
}>();

function displayValue(value: unknown): string {
  return props.options.find((option) => option.value === value)?.label ?? "";
}

function updateValue(value: unknown): void {
  emit("update:modelValue", typeof value === "number" ? value : null);
}
</script>

<template>
  <ComboboxRoot
    :model-value="modelValue"
    :disabled="disabled"
    :reset-model-value-on-clear="true"
    open-on-click
    @update:model-value="updateValue"
  >
    <ComboboxAnchor class="tf-combobox-anchor">
      <ComboboxInput
        class="tf-combobox-input"
        :display-value="displayValue"
        :placeholder="placeholder"
      />
      <ComboboxTrigger class="tf-combobox-trigger" :aria-label="placeholder">
        <ChevronDown :size="16" aria-hidden="true" />
      </ComboboxTrigger>
    </ComboboxAnchor>
    <ComboboxPortal>
      <ComboboxContent
        class="tf-combobox-content"
        position="popper"
        :side-offset="6"
      >
        <ComboboxViewport class="tf-combobox-viewport">
          <ComboboxEmpty class="tf-combobox-empty">
            {{ emptyLabel }}
          </ComboboxEmpty>
          <ComboboxItem
            v-for="option in options"
            :key="option.value"
            class="tf-combobox-item"
            :value="option.value"
            :text-value="`${option.label} ${option.detail ?? ''}`"
          >
            <span>
              <strong>{{ option.label }}</strong>
              <small v-if="option.detail">{{ option.detail }}</small>
            </span>
            <ComboboxItemIndicator class="tf-combobox-indicator">
              <Check :size="15" aria-hidden="true" />
            </ComboboxItemIndicator>
          </ComboboxItem>
        </ComboboxViewport>
      </ComboboxContent>
    </ComboboxPortal>
  </ComboboxRoot>
</template>

<script setup lang="ts">
import { Check, ChevronDown } from "@lucide/vue";
import { ref, watch } from "vue";
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
  remote?: boolean;
  hasMore?: boolean;
  busy?: boolean;
  error?: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: number | null];
  search: [value: string];
  open: [value: boolean];
  "load-more": [];
  retry: [];
}>();

function displayValue(value: unknown): string {
  return props.options.find((option) => option.value === value)?.label ?? "";
}

const isOpen = ref(false);
const inputText = ref(displayValue(props.modelValue));
watch(
  () => [props.modelValue, props.options],
  () => {
    if (!isOpen.value) inputText.value = displayValue(props.modelValue);
  },
);
function updateOpen(value: boolean): void {
  isOpen.value = value;
  if (!value) inputText.value = displayValue(props.modelValue);
  else emit("search", "");
  emit("open", value);
}

function searchInput(event: Event): void {
  if (event.target instanceof HTMLInputElement) {
    emit("search", event.target.value);
  }
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
    :ignore-filter="remote"
    @update:open="updateOpen"
    @update:model-value="updateValue"
  >
    <ComboboxAnchor class="tf-combobox-anchor">
      <ComboboxInput
        v-model="inputText"
        class="tf-combobox-input"
        :display-value="displayValue"
        :placeholder="placeholder"
        @input="searchInput"
      />
      <ComboboxTrigger class="tf-combobox-trigger" :aria-label="placeholder">
        <ChevronDown :size="16" aria-hidden="true" />
      </ComboboxTrigger>
    </ComboboxAnchor>
    <ComboboxPortal to=".tf-app">
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
          <button
            v-if="error"
            class="button-link"
            type="button"
            @click.stop="emit('retry')"
          >
            {{ $t("pagination.retry") }}
          </button>
          <button
            v-else-if="hasMore"
            class="button-link"
            type="button"
            :disabled="busy"
            @click.stop="emit('load-more')"
          >
            {{ $t("pagination.more") }}
          </button>
        </ComboboxViewport>
      </ComboboxContent>
    </ComboboxPortal>
  </ComboboxRoot>
</template>

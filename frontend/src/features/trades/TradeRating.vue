<script setup lang="ts">
import { Star } from "@lucide/vue";
import { computed, ref } from "vue";

const props = defineProps<{
  modelValue: number | null;
  label: string;
  emptyLabel: string;
  valueLabel: (value: number) => string;
  disabled?: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [value: number | null] }>();
const hoveredValue = ref<number | null>(null);
const visibleValue = computed(
  () => hoveredValue.value ?? props.modelValue ?? 0,
);
const slots = [0, 1, 2, 3, 4];

function valueFromPointer(event: PointerEvent, slot: number): number {
  const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const half = event.clientX - bounds.left <= bounds.width / 2 ? 1 : 2;
  return slot * 2 + half;
}

function preview(event: PointerEvent, slot: number): void {
  if (!props.disabled) hoveredValue.value = valueFromPointer(event, slot);
}

function commit(event: PointerEvent, slot: number): void {
  if (props.disabled) return;
  const value = valueFromPointer(event, slot);
  emit("update:modelValue", value === props.modelValue ? null : value);
  hoveredValue.value = null;
}

function fill(slot: number): string {
  const remainder = visibleValue.value - slot * 2;
  return `${remainder <= 0 ? 0 : remainder === 1 ? 50 : 100}%`;
}

function setFromKeyboard(value: number | null): void {
  if (!props.disabled) emit("update:modelValue", value);
}

function adjust(delta: number): void {
  const current = props.modelValue ?? (delta > 0 ? 0 : 11);
  setFromKeyboard(Math.min(10, Math.max(1, current + delta)));
}
</script>

<template>
  <div class="trade-rating">
    <span>{{ label }}</span>
    <div
      class="trade-rating__control"
      :class="{ 'trade-rating__control--disabled': disabled }"
      role="slider"
      tabindex="0"
      aria-valuemin="1"
      aria-valuemax="10"
      :aria-label="label"
      :aria-valuenow="modelValue ?? undefined"
      :aria-valuetext="
        modelValue === null ? emptyLabel : valueLabel(modelValue)
      "
      @mouseleave="hoveredValue = null"
      @keydown.left.prevent="adjust(-1)"
      @keydown.down.prevent="adjust(-1)"
      @keydown.right.prevent="adjust(1)"
      @keydown.up.prevent="adjust(1)"
      @keydown.home.prevent="setFromKeyboard(1)"
      @keydown.end.prevent="setFromKeyboard(10)"
      @keydown.delete.prevent="setFromKeyboard(null)"
      @keydown.backspace.prevent="setFromKeyboard(null)"
    >
      <button
        v-for="slot in slots"
        :key="slot"
        type="button"
        tabindex="-1"
        :disabled="disabled"
        :aria-label="valueLabel(slot * 2 + 2)"
        @pointermove="preview($event, slot)"
        @click="commit($event, slot)"
      >
        <Star :size="19" aria-hidden="true" />
        <span :style="{ width: fill(slot) }">
          <Star :size="19" aria-hidden="true" />
        </span>
      </button>
    </div>
    <small>{{
      modelValue === null ? emptyLabel : valueLabel(modelValue)
    }}</small>
  </div>
</template>

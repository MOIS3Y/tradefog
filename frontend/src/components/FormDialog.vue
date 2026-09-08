<script setup lang="ts">
import { X } from "@lucide/vue";
import {
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from "reka-ui";

defineProps<{
  open: boolean;
  title: string;
  description: string;
  submitLabel: string;
  cancelLabel: string;
  busy?: boolean;
  invalid?: boolean;
}>();

const emit = defineEmits<{
  submit: [];
  "update:open": [value: boolean];
}>();
</script>

<template>
  <DialogRoot :open="open" @update:open="emit('update:open', $event)">
    <DialogPortal to=".tf-app">
      <DialogOverlay class="tf-overlay" />
      <DialogContent class="tf-form-dialog">
        <header class="tf-form-dialog__header">
          <div>
            <DialogTitle class="tf-form-dialog__title">{{ title }}</DialogTitle>
            <DialogDescription class="tf-form-dialog__description">
              {{ description }}
            </DialogDescription>
          </div>
          <DialogClose class="tf-form-dialog__close" :aria-label="cancelLabel">
            <X :size="17" aria-hidden="true" />
          </DialogClose>
        </header>
        <form class="tf-form" @submit.prevent="emit('submit')">
          <slot />
          <div class="tf-dialog-actions">
            <DialogClose class="button button--secondary" :disabled="busy">
              {{ cancelLabel }}
            </DialogClose>
            <button
              class="button button--primary"
              type="submit"
              :disabled="busy || invalid"
            >
              {{ submitLabel }}
            </button>
          </div>
        </form>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>

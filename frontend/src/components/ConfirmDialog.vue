<script setup lang="ts">
import { AlertTriangle } from "@lucide/vue";
import {
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
} from "reka-ui";

defineProps<{
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel: string;
  busy?: boolean;
}>();

const emit = defineEmits<{
  confirm: [];
  "update:open": [value: boolean];
}>();
</script>

<template>
  <AlertDialogRoot :open="open" @update:open="emit('update:open', $event)">
    <AlertDialogPortal to=".tf-app">
      <AlertDialogOverlay class="tf-overlay" />
      <AlertDialogContent class="tf-confirm-dialog">
        <span class="tf-confirm-dialog__signal" aria-hidden="true">
          <AlertTriangle :size="17" />
        </span>
        <AlertDialogTitle class="tf-confirm-dialog__title">
          {{ title }}
        </AlertDialogTitle>
        <AlertDialogDescription class="tf-confirm-dialog__body">
          {{ description }}
        </AlertDialogDescription>
        <div class="tf-dialog-actions">
          <AlertDialogCancel class="button button--secondary" :disabled="busy">
            {{ cancelLabel }}
          </AlertDialogCancel>
          <button
            class="button button--danger"
            type="button"
            :disabled="busy"
            @click="emit('confirm')"
          >
            {{ confirmLabel }}
          </button>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>

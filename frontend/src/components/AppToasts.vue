<script setup lang="ts">
import { X } from "@lucide/vue";
import {
  ToastClose,
  ToastDescription,
  ToastPortal,
  ToastProvider,
  ToastRoot,
  ToastTitle,
  ToastViewport,
} from "reka-ui";
import { useI18n } from "vue-i18n";

import { useToastStore } from "@/stores/toasts";

const toasts = useToastStore();
const { t } = useI18n();
</script>

<template>
  <ToastProvider :label="t('common.notification')" swipe-direction="right">
    <ToastRoot
      v-for="message in toasts.messages"
      :key="message.id"
      :class="['tf-toast', `tf-toast--${message.kind}`]"
      :duration="message.duration"
      :open="true"
      type="foreground"
      @update:open="!$event && toasts.remove(message.id)"
    >
      <span class="tf-toast__signal" aria-hidden="true"></span>
      <span class="tf-toast__copy">
        <ToastTitle class="tf-toast__title">{{ message.title }}</ToastTitle>
        <ToastDescription v-if="message.description" class="tf-toast__body">
          {{ message.description }}
        </ToastDescription>
      </span>
      <ToastClose class="tf-toast__close" :aria-label="t('common.close')">
        <X :size="15" aria-hidden="true" />
      </ToastClose>
    </ToastRoot>
    <ToastPortal to=".tf-app">
      <ToastViewport class="tf-toast-viewport" />
    </ToastPortal>
  </ToastProvider>
</template>

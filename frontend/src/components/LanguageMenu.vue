<script setup lang="ts">
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuTrigger,
} from "reka-ui";
import { useI18n } from "vue-i18n";

import { setLocale } from "@/i18n";

const { locale } = useI18n();
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger
      class="language-trigger"
      :aria-label="$t('common.language')"
    >
      <span>{{ locale.toUpperCase() }}</span>
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="m4.5 6 3.5 3.5L11.5 6" />
      </svg>
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent
        class="tf-language-menu"
        :side-offset="8"
        align="end"
      >
        <DropdownMenuItem class="tf-language-item" @select="setLocale('en')">
          <span>English</span>
          <span v-if="locale === 'en'" aria-hidden="true">●</span>
        </DropdownMenuItem>
        <DropdownMenuItem class="tf-language-item" @select="setLocale('ru')">
          <span>Русский</span>
          <span v-if="locale === 'ru'" aria-hidden="true">●</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>

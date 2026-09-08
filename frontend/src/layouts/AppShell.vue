<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import BrandMark from "@/components/BrandMark.vue";
import LanguageMenu from "@/components/LanguageMenu.vue";
import PositionDiagram from "@/components/PositionDiagram.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { t } = useI18n();
const router = useRouter();
const navigationOpen = ref(false);

const navigation = computed(() => [
  { label: t("nav.overview"), active: true },
  { label: t("nav.catalog"), active: false },
  { label: t("nav.profiles"), active: false },
  { label: t("nav.trades"), active: false },
  { label: t("nav.analytics"), active: false },
]);

const initials = computed(() =>
  (auth.user?.username ?? "TF").slice(0, 2).toUpperCase(),
);

async function signOut(): Promise<void> {
  auth.signOut();
  await router.replace("/login");
}
</script>

<template>
  <div class="app-frame">
    <header class="mobile-header">
      <a class="wordmark" href="/" aria-label="Tradefog home">
        <BrandMark />
        <span>Tradefog</span>
      </a>
      <button
        class="icon-button"
        type="button"
        :aria-expanded="navigationOpen"
        aria-controls="primary-navigation"
        @click="navigationOpen = !navigationOpen"
      >
        <span class="menu-lines" aria-hidden="true"></span>
        <span class="sr-only">{{ $t("common.menu") }}</span>
      </button>
    </header>

    <aside
      id="primary-navigation"
      class="sidebar"
      :class="{ 'sidebar--open': navigationOpen }"
    >
      <a class="wordmark wordmark--desktop" href="/" aria-label="Tradefog home">
        <BrandMark />
        <span>Tradefog</span>
      </a>

      <PositionDiagram />

      <nav class="primary-nav" aria-label="Primary navigation">
        <div
          v-for="item in navigation"
          :key="item.label"
          class="nav-item"
          :class="{ 'nav-item--active': item.active }"
          :aria-current="item.active ? 'page' : undefined"
        >
          <span class="nav-item__marker" aria-hidden="true"></span>
          <span>{{ item.label }}</span>
          <small v-if="!item.active">{{ $t("nav.next") }}</small>
        </div>
      </nav>

      <div class="sidebar__footer">
        <LanguageMenu />
        <div class="account-card">
          <span class="account-card__avatar">{{ initials }}</span>
          <span class="account-card__identity">
            <strong>{{ auth.user?.username }}</strong>
            <small>
              {{
                auth.user?.is_staff
                  ? $t("dashboard.staff")
                  : $t("dashboard.user")
              }}
            </small>
          </span>
          <button class="sign-out" type="button" @click="signOut">
            {{ $t("common.signOut") }}
          </button>
        </div>
      </div>
    </aside>

    <main class="app-content">
      <slot />
    </main>
  </div>
</template>

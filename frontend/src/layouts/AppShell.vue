<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import BrandMark from "@/components/BrandMark.vue";
import { Settings } from "@lucide/vue";
import PositionDiagram from "@/components/PositionDiagram.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const navigationOpen = ref(false);

const navigation = computed(() => [
  { label: t("nav.overview"), path: "/", active: route.path === "/" },

  {
    label: t("nav.profiles"),
    path: "/profiles",
    active: route.path.startsWith("/profiles"),
  },
  {
    label: t("nav.trades"),
    path: "/trades",
    active: route.path.startsWith("/trades"),
  },
  {
    label: t("nav.analytics"),
    path: "/analytics",
    active: route.path.startsWith("/analytics"),
  },
]);

const initials = computed(() =>
  (auth.user?.username ?? "TF").slice(0, 2).toUpperCase(),
);

/** Prefer personal details while retaining a localized role fallback. */
const accountCaption = computed(() => {
  const user = auth.user;
  const name = [user?.first_name, user?.last_name]
    .map((part) => part?.trim())
    .filter(Boolean)
    .join(" ");
  return (
    name ||
    user?.email?.trim() ||
    t(user?.is_staff ? "dashboard.staff" : "dashboard.user")
  );
});

async function signOut(): Promise<void> {
  auth.signOut();
  await router.replace("/login");
}

function closeNavigation(): void {
  navigationOpen.value = false;
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
        <component
          v-for="item in navigation"
          :key="item.label"
          :is="item.path ? 'RouterLink' : 'div'"
          :to="item.path"
          class="nav-item"
          :class="{ 'nav-item--active': item.active }"
          :aria-current="item.active ? 'page' : undefined"
          @click="item.path && closeNavigation()"
        >
          <span class="nav-item__marker" aria-hidden="true"></span>
          <span>{{ item.label }}</span>
        </component>
      </nav>

      <div class="sidebar__footer">
        <RouterLink
          to="/settings"
          class="account-settings-link"
          :aria-current="route.path === '/settings' ? 'page' : undefined"
          @click="closeNavigation"
        >
          <Settings :size="17" aria-hidden="true" />
          {{ t("settings.title") }}
        </RouterLink>
        <div class="account-card">
          <span class="account-card__avatar">{{ initials }}</span>
          <span class="account-card__identity">
            <strong>{{ auth.user?.username }}</strong>
            <small :title="accountCaption">{{ accountCaption }}</small>
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

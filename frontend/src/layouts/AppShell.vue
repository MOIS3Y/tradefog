<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { useIsMutating } from "@tanstack/vue-query";
import { useProfileContext } from "@/composables/useProfileContext";
import {
  leaveConfirmation,
  answerLeave,
  useNavigationBusy,
  confirmNavigation,
} from "@/composables/useLeaveGuard";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import ProfileContextSelect from "@/components/ProfileContextSelect.vue";
import ProfileScopeBoundary from "@/components/ProfileScopeBoundary.vue";
import BrandMark from "@/components/BrandMark.vue";
import {
  Settings,
  LayoutDashboard,
  WalletCards,
  ArrowLeftRight,
  ChartNoAxesCombined,
  PanelLeftClose,
  PanelLeftOpen,
  LogOut,
} from "@lucide/vue";
import { TooltipProvider } from "reka-ui";
import SidebarTooltip from "@/components/SidebarTooltip.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { prefix, profileId } = useProfileContext();
const mutations = useIsMutating();
useNavigationBusy(mutations);
const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const navigationOpen = ref(false);
const storageKey = "tradefog.sidebar.collapsed";

/** Restore the local layout preference without requiring browser storage. */
function readCollapsed(): boolean {
  try {
    return localStorage.getItem(storageKey) === "true";
  } catch {
    return false;
  }
}

const collapsed = ref(readCollapsed());
const desktopQuery = window.matchMedia?.("(min-width: 921px)");
const desktop = ref(desktopQuery?.matches ?? true);
const compact = computed(() => collapsed.value && desktop.value);
const toggleLabel = computed(() =>
  t(collapsed.value ? "nav.expand" : "nav.collapse"),
);

/** Keep desktop tooltips independent from the mobile menu. */
function updateDesktop(): void {
  desktop.value = desktopQuery?.matches ?? true;
  navigationOpen.value = false;
}

/** Persist only a presentation preference; storage errors are harmless. */
function toggleCollapsed(): void {
  collapsed.value = !collapsed.value;
  try {
    localStorage.setItem(storageKey, String(collapsed.value));
  } catch {
    // The current session can still use the chosen layout.
  }
}

onMounted(() => desktopQuery?.addEventListener("change", updateDesktop));
onBeforeUnmount(() =>
  desktopQuery?.removeEventListener("change", updateDesktop),
);

const navigation = computed(() => [
  {
    label: t("nav.profiles"),
    icon: WalletCards,
    path: "/profiles",
    active: route.path === "/profiles",
  },
  {
    label: t("nav.trades"),
    icon: ArrowLeftRight,
    path: `${prefix.value}/trades`,
    active: route.path.includes("/trades"),
  },
  {
    label: t("nav.analytics"),
    icon: ChartNoAxesCombined,
    path: `${prefix.value}/analytics`,
    active: route.path.endsWith("/analytics"),
  },
]);

const profileNavigation = computed(() =>
  profileId.value === null
    ? []
    : [
        {
          label: t("profileMarket.title"),
          icon: LayoutDashboard,
          path: `${prefix.value}/market`,
        },
        {
          label: t("profiles.wallet.tab"),
          icon: WalletCards,
          path: `${prefix.value}/wallet`,
        },
        {
          label: t("profiles.strategies.tab"),
          icon: ChartNoAxesCombined,
          path: `${prefix.value}/strategies`,
        },
      ].map((item) => ({ ...item, active: route.path === item.path })),
);

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
  if (!(await confirmNavigation())) return;
  auth.signOut();
  await router.replace("/login");
}

function closeNavigation(): void {
  navigationOpen.value = false;
}
</script>

<template>
  <TooltipProvider :delay-duration="250">
    <div class="app-frame" :class="{ 'app-frame--collapsed': collapsed }">
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
        <div class="sidebar__heading">
          <a
            class="wordmark wordmark--desktop"
            href="/"
            aria-label="Tradefog home"
          >
            <BrandMark />
            <span class="sidebar__label">Tradefog</span>
          </a>
          <SidebarTooltip :label="toggleLabel" :disabled="!compact">
            <button
              class="sidebar__toggle"
              type="button"
              :aria-label="toggleLabel"
              :aria-expanded="!collapsed"
              aria-controls="sidebar-navigation"
              @click="toggleCollapsed"
            >
              <component
                :is="collapsed ? PanelLeftOpen : PanelLeftClose"
                :size="18"
                aria-hidden="true"
              />
            </button>
          </SidebarTooltip>
        </div>

        <ProfileContextSelect :compact="compact" />

        <nav
          id="sidebar-navigation"
          class="primary-nav"
          :aria-label="t('common.menu')"
        >
          <SidebarTooltip
            v-for="item in [...navigation, ...profileNavigation]"
            :key="item.path"
            :label="item.label"
            :disabled="!compact"
          >
            <RouterLink
              :to="item.path"
              :aria-label="item.label"
              class="nav-item"
              :class="{ 'nav-item--active': item.active }"
              :aria-current="item.active ? 'page' : undefined"
              @click="item.path && closeNavigation()"
            >
              <component
                :is="item.icon"
                :size="19"
                class="nav-item__icon"
                aria-hidden="true"
              />
              <span class="sidebar__label">{{ item.label }}</span>
            </RouterLink>
          </SidebarTooltip>
        </nav>

        <div class="sidebar__footer">
          <SidebarTooltip :label="t('settings.title')" :disabled="!compact">
            <RouterLink
              to="/settings"
              :aria-label="t('settings.title')"
              class="nav-item account-settings-link"
              :class="{ 'nav-item--active': route.path === '/settings' }"
              :aria-current="route.path === '/settings' ? 'page' : undefined"
              @click="closeNavigation"
            >
              <Settings :size="19" class="nav-item__icon" aria-hidden="true" />
              <span class="sidebar__label">{{ t("settings.title") }}</span>
            </RouterLink>
          </SidebarTooltip>
          <div class="account-card">
            <SidebarTooltip
              :label="auth.user?.username ?? initials"
              :disabled="!compact"
            >
              <span
                class="account-card__avatar"
                :tabindex="compact ? 0 : undefined"
                :aria-label="auth.user?.username ?? initials"
                >{{ initials }}</span
              >
            </SidebarTooltip>
            <span class="account-card__identity">
              <strong>{{ auth.user?.username }}</strong>
              <small :title="accountCaption">{{ accountCaption }}</small>
            </span>
            <SidebarTooltip :label="t('common.signOut')" :disabled="!compact">
              <button
                class="sign-out"
                type="button"
                :aria-label="t('common.signOut')"
                @click="signOut"
              >
                <LogOut class="sign-out__icon" :size="18" aria-hidden="true" />
                <span class="sidebar__label">{{ $t("common.signOut") }}</span>
              </button>
            </SidebarTooltip>
          </div>
        </div>
      </aside>

      <main class="app-content">
        <ProfileScopeBoundary><slot /></ProfileScopeBoundary>
      </main>
    </div>
    <ConfirmDialog
      :open="leaveConfirmation"
      :title="$t('context.unsavedTitle')"
      :description="$t('context.unsavedBody')"
      :confirm-label="$t('context.discard')"
      :cancel-label="$t('context.stay')"
      :busy="mutations > 0"
      @confirm="answerLeave(true)"
      @update:open="answerLeave(false)"
    />
  </TooltipProvider>
</template>

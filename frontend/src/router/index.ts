import type { Pinia } from "pinia";
import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from "vue-router";

import { useAuthStore } from "@/stores/auth";

import { getProfile } from "@/features/profiles/api";
import { ApiError } from "@/api/errors";
import {
  readProfileContext,
  rememberProfileContext,
} from "@/composables/useProfileContext";
import { confirmNavigation } from "@/composables/useLeaveGuard";
import LoginView from "@/views/LoginView.vue";
import NotFoundView from "@/views/NotFoundView.vue";
import ProfilesView from "@/views/ProfilesView.vue";
import TradesView from "@/views/TradesView.vue";

const routes: RouteRecordRaw[] = [
  {
    path: "/settings",
    component: () => import("@/views/SettingsView.vue"),
    meta: { requiresAuth: true },
  },
  { path: "/", component: TradesView, meta: { requiresAuth: true } },
  {
    path: "/profiles",
    component: ProfilesView,
    meta: { requiresAuth: true },
  },
  {
    path: "/trades",
    component: TradesView,
    meta: { requiresAuth: true },
  },
  {
    path: "/profiles/:profileId(\\d+)",
    redirect: (to) => `/profiles/${to.params.profileId}/trades`,
    meta: { requiresAuth: true },
  },
  {
    path: "/profiles/:profileId(\\d+)/trades/:tradeId(\\d+)?",
    component: TradesView,
    meta: { requiresAuth: true },
  },
  {
    path: "/profiles/:profileId(\\d+)/:section(market|wallet|strategies)",
    component: ProfilesView,
    meta: { requiresAuth: true },
  },
  {
    path: "/profiles/:profileId(\\d+)/analytics",
    component: () => import("@/views/AnalyticsView.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/analytics",
    component: () => import("@/views/AnalyticsView.vue"),
    meta: { requiresAuth: true },
  },
  { path: "/login", component: LoginView, meta: { guestOnly: true } },
  { path: "/:pathMatch(.*)*", component: NotFoundView },
];

export function createAppRouter(pinia: Pinia) {
  const router = createRouter({
    history: createWebHistory(),
    routes,
    scrollBehavior: () => ({ top: 0 }),
  });

  router.beforeEach(async (to) => {
    const auth = useAuthStore(pinia);
    await auth.bootstrap();

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { path: "/login", query: { redirect: to.fullPath } };
    }
    if (to.meta.guestOnly && auth.isAuthenticated) {
      return { path: "/" };
    }
    if (to.path === "/" && auth.user) {
      const profileId = readProfileContext(auth.user.id);
      if (profileId !== null) {
        try {
          await getProfile(profileId);
          return `/profiles/${profileId}/trades`;
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 404) throw error;
          rememberProfileContext(auth.user.id, null);
        }
      }
      return "/trades";
    }
    return auth.isAuthenticated ? confirmNavigation() : true;
  });
  router.afterEach((to, _from, failure) => {
    const auth = useAuthStore(pinia);
    if (failure || !auth.user) return;
    if (["/trades", "/analytics"].includes(to.path)) {
      rememberProfileContext(auth.user.id, null);
    }
  });

  return router;
}

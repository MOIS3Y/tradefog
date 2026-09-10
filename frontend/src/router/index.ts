import type { Pinia } from "pinia";
import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from "vue-router";

import { useAuthStore } from "@/stores/auth";

import DashboardView from "@/views/DashboardView.vue";
import LoginView from "@/views/LoginView.vue";
import NotFoundView from "@/views/NotFoundView.vue";
import ProfilesView from "@/views/ProfilesView.vue";
import TradesView from "@/views/TradesView.vue";

const routes: RouteRecordRaw[] = [
  { path: "/", component: DashboardView, meta: { requiresAuth: true } },
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
    path: "/trades/new",
    component: TradesView,
    meta: { requiresAuth: true },
  },
  {
    path: "/trades/:tradeId(\\d+)",
    component: TradesView,
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
    return true;
  });

  return router;
}

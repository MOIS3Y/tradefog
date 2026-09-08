import type { Pinia } from "pinia";
import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from "vue-router";

import { useAuthStore } from "@/stores/auth";
import CatalogView from "@/views/CatalogView.vue";
import DashboardView from "@/views/DashboardView.vue";
import LoginView from "@/views/LoginView.vue";
import NotFoundView from "@/views/NotFoundView.vue";

const routes: RouteRecordRaw[] = [
  { path: "/", component: DashboardView, meta: { requiresAuth: true } },
  {
    path: "/catalog",
    redirect: "/catalog/assets",
  },
  {
    path: "/catalog/assets",
    component: CatalogView,
    props: { section: "assets" },
    meta: { requiresAuth: true },
  },
  {
    path: "/catalog/pairs",
    component: CatalogView,
    props: { section: "pairs" },
    meta: { requiresAuth: true },
  },
  {
    path: "/catalog/venues",
    component: CatalogView,
    props: { section: "venues" },
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

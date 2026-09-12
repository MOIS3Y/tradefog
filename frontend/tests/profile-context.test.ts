/** Context routing keeps working profiles separate from aggregate views. */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, h, ref, type App } from "vue";
import { createPinia } from "pinia";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import { createAppRouter } from "@/router";
import ProfileContextSelect from "@/components/ProfileContextSelect.vue";
import { i18n } from "@/i18n";
import {
  answerLeave,
  leaveConfirmation,
  useLeaveGuard,
  useNavigationBusy,
} from "@/composables/useLeaveGuard";
import {
  readProfileContext,
  rememberProfileContext,
} from "@/composables/useProfileContext";

vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({
    user: { id: 9 },
    isAuthenticated: true,
    bootstrap: async () => {},
  }),
}));

let app: App | undefined;
let client: QueryClient | undefined;
const dirty = ref(false);
const busy = ref(0);

beforeEach(() => {
  localStorage.clear();
  history.replaceState({}, "", "/");
  dirty.value = false;
  busy.value = 0;
  i18n.global.locale.value = "en";
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const path = new URL(request.url).pathname;
      const profiles = [
        { id: 1, name: "Bybit", is_archived: false },
        { id: 2, name: "Manual", is_archived: false },
        { id: 3, name: "History", is_archived: true },
      ];
      const profile = profiles.find((item) =>
        path.endsWith(`/profiles/${item.id}`),
      );
      const data = path.endsWith("/profiles")
        ? { items: profiles, total: profiles.length }
        : profile;
      return new Response(JSON.stringify(data ?? { detail: "Not found" }), {
        status: data ? 200 : 404,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  answerLeave(false);
  app?.unmount();
  client?.clear();
  app = undefined;
  client = undefined;
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

/** Mount the production router and selector without rendering trade forms. */
async function mount(path: string) {
  const pinia = createPinia();
  const router = createAppRouter(pinia);
  await router.push(path);
  await router.isReady();
  document.body.innerHTML = '<div id="root"></div>';
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  app = createApp({
    setup() {
      useLeaveGuard(dirty);
      useNavigationBusy(busy);
      return () => h(ProfileContextSelect);
    },
  });
  app
    .use(pinia)
    .use(router)
    .use(i18n)
    .use(VueQueryPlugin, { queryClient: client })
    .mount("#root");
  await vi.waitFor(() =>
    expect(
      document.querySelector<HTMLButtonElement>(".profile-context__trigger")
        ?.disabled,
    ).toBe(false),
  );
  return router;
}

/** Select an explicit destination in the same control used on mobile. */
async function choose(profileId: number | null): Promise<void> {
  const trigger = document.querySelector<HTMLButtonElement>(
    ".profile-context__trigger",
  )!;
  trigger.dispatchEvent(
    new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
  );
  await vi.waitFor(() =>
    expect(document.querySelectorAll('[role="menuitemradio"]')).toHaveLength(4),
  );
  const index = profileId === null ? 0 : profileId;
  document
    .querySelectorAll<HTMLElement>('[role="menuitemradio"]')
    [index]!.click();
}

it("retains the section and common filters, dropping resource identities", async () => {
  const router = await mount(
    "/profiles/1/trades?strategy_id=7&page=3&q=BTC&trade_status=open&order=asc",
  );
  await choose(2);
  await vi.waitFor(() =>
    expect(router.currentRoute.value.path).toBe("/profiles/2/trades"),
  );
  expect(router.currentRoute.value.query).toEqual({
    trade_status: "open",
    order: "asc",
  });
  await router.push("/profiles/2/trades/42");
  await choose(1);
  await vi.waitFor(() =>
    expect(router.currentRoute.value.path).toBe("/profiles/1/trades"),
  );
  await router.push("/profiles/1/wallet");
  await choose(null);
  await vi.waitFor(() =>
    expect(router.currentRoute.value.path).toBe("/trades"),
  );
  await choose(3);
  await vi.waitFor(() =>
    expect(router.currentRoute.value.path).toBe("/profiles/3/trades"),
  );
});

it("keeps dirty forms in place until confirmed and blocks in-flight writes", async () => {
  const router = await mount("/profiles/1/trades/42");
  dirty.value = true;
  await choose(2);
  await vi.waitFor(() => expect(leaveConfirmation.value).toBe(true));
  answerLeave(false);
  expect(router.currentRoute.value.path).toBe("/profiles/1/trades/42");
  await choose(2);
  await vi.waitFor(() => expect(leaveConfirmation.value).toBe(true));
  answerLeave(true);
  await vi.waitFor(() =>
    expect(router.currentRoute.value.path).toBe("/profiles/2/trades"),
  );
  dirty.value = false;
  busy.value = 1;
  await router.push("/profiles/1/trades");
  expect(router.currentRoute.value.path).toBe("/profiles/2/trades");
});

it("restores per-user preferences only at the entry point", async () => {
  rememberProfileContext(9, 2);
  rememberProfileContext(10, 1);
  const router = await mount("/profiles/1/analytics");
  expect(router.currentRoute.value.params.profileId).toBe("1");
  await router.push("/");
  expect(router.currentRoute.value.path).toBe("/profiles/2/trades");
  expect(readProfileContext(10)).toBe(1);
  rememberProfileContext(9, 999);
  await router.push("/");
  expect(router.currentRoute.value.path).toBe("/trades");
  expect(readProfileContext(9)).toBeNull();
});

/** Sidebar preferences must not replace page state or mobile navigation. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import AppShell from "@/layouts/AppShell.vue";
import { i18n } from "@/i18n";

let app: App | undefined;
const key = "tradefog.sidebar.collapsed";

afterEach(() => {
  app?.unmount();
  app = undefined;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  document.body.innerHTML = "";
});

/** Mount a real shell with controllable breakpoint events. */
async function mount() {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ items: [], total: 0 }), {
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
  const media = new EventTarget();
  Object.assign(media, { matches: true });
  vi.stubGlobal("matchMedia", () => media);
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:pathMatch(.*)*", component: { render: () => null } }],
  });
  await router.push("/trades/1");
  i18n.global.locale.value = "en";
  document.body.innerHTML = '<div id="root"></div>';
  app = createApp({
    render: () =>
      h(AppShell, null, { default: () => h("input", { id: "draft" }) }),
  });
  app
    .use(createPinia())
    .use(router)
    .use(i18n)
    .use(VueQueryPlugin, {
      queryClient: new QueryClient({
        defaultOptions: { queries: { retry: false } },
      }),
    })
    .mount("#root");
  await nextTick();
  return { media, router };
}

/** Activate the persistent desktop preference. */
async function toggle() {
  document.querySelector<HTMLButtonElement>(".sidebar__toggle")!.click();
  await nextTick();
}

it("preserves content and active navigation while saving and restoring width", async () => {
  await mount();
  const draft = document.querySelector<HTMLInputElement>("#draft")!;
  draft.value = "unsaved";
  expect(
    document
      .querySelector('.nav-item[aria-current="page"]')
      ?.getAttribute("href"),
  ).toBe("/trades");
  await toggle();
  expect(localStorage.getItem(key)).toBe("true");
  expect(document.querySelector(".app-frame--collapsed")).not.toBeNull();
  expect(document.querySelector("#draft")).toBe(draft);
  expect(draft.value).toBe("unsaved");
  app!.unmount();
  await mount();
  expect(
    document.querySelector(".sidebar__toggle")?.getAttribute("aria-expanded"),
  ).toBe("false");
  await toggle();
  expect(localStorage.getItem(key)).toBe("false");
});

it("keeps the mobile menu independent and restores desktop compact controls", async () => {
  localStorage.setItem(key, "true");
  const { media } = await mount();
  Object.assign(media, { matches: false });
  media.dispatchEvent(new Event("change"));
  await nextTick();
  expect(
    document.querySelector(".account-card__avatar")?.hasAttribute("tabindex"),
  ).toBe(false);
  document.querySelector<HTMLButtonElement>(".mobile-header button")!.click();
  await nextTick();
  expect(document.querySelector(".sidebar--open")).not.toBeNull();
  document
    .querySelector<HTMLAnchorElement>('.nav-item[href="/profiles"]')!
    .click();
  await nextTick();
  expect(document.querySelector(".sidebar--open")).toBeNull();
  Object.assign(media, { matches: true });
  media.dispatchEvent(new Event("change"));
  await nextTick();
  expect(
    document.querySelector(".account-card__avatar")?.getAttribute("tabindex"),
  ).toBe("0");
  expect(localStorage.getItem(key)).toBe("true");
});

it("still toggles when storage cannot be read or written", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  await mount();
  await toggle();
  expect(document.querySelector(".app-frame--collapsed")).not.toBeNull();
});

/** Settings preserve drafts on errors and apply only saved preferences. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import SettingsView from "@/views/SettingsView.vue";
import { updateAccount, changePassword } from "@/features/settings/api";
import { ApiError } from "@/api/errors";
import { getTokens, setTokens } from "@/api/tokens";
import { useAuthStore } from "@/stores/auth";
import { i18n, setLocale } from "@/i18n";

vi.mock("@/features/settings/api", () => ({
  updateAccount: vi.fn(),
  changePassword: vi.fn(),
}));
let app: App;
let query: QueryClient;
afterEach(() => {
  app?.unmount();
  query?.clear();
  vi.resetAllMocks();
  document.body.innerHTML = "";
  localStorage.clear();
});
const user = {
  id: 1,
  username: "alice",
  first_name: null,
  last_name: null,
  email: null,
  preferred_locale: null,
  is_staff: false,
  is_active: true,
  created_at: "2026-09-11T12:00:00",
  updated_at: "2026-09-11T12:00:00",
};

/** Mount the real page and auth store with isolated mutation state. */
async function mount(tab = "account") {
  document.body.innerHTML = '<div class="tf-app"><div id="root"></div></div>';
  setLocale("en");
  const pinia = createPinia();
  const auth = useAuthStore(pinia);
  auth.acceptUser(user);
  auth.status = "authenticated";
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/settings", component: SettingsView },
      { path: "/login", component: { template: "<p>Login</p>" } },
      { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
    ],
  });
  await router.push(`/settings?tab=${tab}`);
  query = new QueryClient();
  app = createApp({ template: "<RouterView />" });
  app
    .use(pinia)
    .use(router)
    .use(i18n)
    .use(VueQueryPlugin, { queryClient: query })
    .mount("#root");
  await nextTick();
  return { auth, router };
}

/** Populate a form through its native input event. */
async function input(selector: string, value: string) {
  const element = document.querySelector<HTMLInputElement>(selector)!;
  element.value = value;
  element.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
}

/** Submit without relying on jsdom's incomplete browser validation. */
function submit() {
  document.querySelector("form")!.dispatchEvent(
    new Event("submit", {
      bubbles: true,
      cancelable: true,
    }),
  );
}

it("preserves account inputs through tab changes and failed saves", async () => {
  const { auth, router } = await mount();
  await input('[autocomplete="given-name"]', "Alice");
  await router.replace("/settings?tab=interface");
  await router.replace("/settings?tab=account");
  await vi.waitFor(() =>
    expect(
      document.querySelector('[autocomplete="given-name"]'),
    ).not.toBeNull(),
  );
  expect(
    document.querySelector<HTMLInputElement>('[autocomplete="given-name"]')!
      .value,
  ).toBe("Alice");
  vi.mocked(updateAccount).mockRejectedValue(new Error("offline"));
  submit();
  await vi.waitFor(() =>
    expect(document.querySelector('[role="alert"]')?.textContent).toContain(
      "Could not save",
    ),
  );
  expect(auth.user?.first_name).toBeNull();
  vi.mocked(updateAccount).mockResolvedValue({ ...user, first_name: "Alice" });
  submit();
  await vi.waitFor(() => expect(auth.user?.first_name).toBe("Alice"));
  expect(updateAccount).toHaveBeenLastCalledWith({
    first_name: "Alice",
    last_name: "",
    email: "",
  });
});

it("changes the language only after the server accepts it", async () => {
  const { auth } = await mount("interface");
  document
    .querySelector<HTMLInputElement>('input[name="language"][value="ru"]')!
    .click();
  await nextTick();
  vi.mocked(updateAccount).mockRejectedValue(new Error("offline"));
  submit();
  await vi.waitFor(() => expect(updateAccount).toHaveBeenCalled());
  expect(i18n.global.locale.value).toBe("en");
  vi.mocked(updateAccount).mockResolvedValue({
    ...user,
    preferred_locale: "ru",
  });
  await vi.waitFor(() =>
    expect(document.querySelector('[role="alert"]')).not.toBeNull(),
  );
  submit();
  await vi.waitFor(() => expect(i18n.global.locale.value).toBe("ru"));
  expect(updateAccount).toHaveBeenLastCalledWith({ preferred_locale: "ru" });
  expect(auth.user?.preferred_locale).toBe("ru");
  expect(document.documentElement.lang).toBe("ru");
  expect(localStorage.getItem("tradefog.locale")).toBe("ru");
});

it.each([
  [" Alice ", " Smith ", "alice@example.com", false, "Alice Smith"],
  [null, "Smith", "alice@example.com", false, "Smith"],
  [" ", null, "alice@example.com", false, "alice@example.com"],
  [null, null, null, false, null],
  [null, null, null, true, null],
] as const)(
  "uses the sidebar identity fallback for %s / %s / %s",
  async (first_name, last_name, email, is_staff, expected) => {
    const { auth } = await mount();
    auth.acceptUser({ ...user, first_name, last_name, email, is_staff });
    await nextTick();
    const caption = document.querySelector(".account-card__identity small")!;
    const text =
      expected ??
      i18n.global.t(is_staff ? "dashboard.staff" : "dashboard.user");
    expect(caption.textContent).toBe(text);
    expect(caption.getAttribute("title")).toBe(text);
  },
);

it("validates confirmation, keeps failed input and ends a successful session", async () => {
  const { auth, router } = await mount("security");
  setTokens({ access_token: "a", refresh_token: "r", token_type: "bearer" });
  await input('[autocomplete="current-password"]', "secret");
  await input('[aria-describedby="password-hint"]', "new password here");
  await input(
    'input[autocomplete="new-password"]:not([aria-describedby])',
    "different password",
  );
  submit();
  await nextTick();
  expect(changePassword).not.toHaveBeenCalled();
  expect(document.querySelector('[role="alert"]')?.textContent).toContain(
    "do not match",
  );
  await input(
    'input[autocomplete="new-password"]:not([aria-describedby])',
    "new password here",
  );
  vi.mocked(changePassword).mockRejectedValue(
    new ApiError(400, "current_password_invalid", "wrong"),
  );
  submit();
  await vi.waitFor(() =>
    expect(document.querySelector('[role="alert"]')?.textContent).toContain(
      "incorrect",
    ),
  );
  expect(auth.isAuthenticated).toBe(true);
  expect(
    document.querySelector<HTMLInputElement>(
      '[autocomplete="current-password"]',
    )!.value,
  ).toBe("secret");
  vi.mocked(changePassword).mockResolvedValue();
  submit();
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe("/login"));
  expect(getTokens()).toBeNull();
  expect(auth.user).toBeNull();
});

it("clears passwords when leaving the security tab", async () => {
  const { router } = await mount("security");
  await input('[autocomplete="current-password"]', "secret");
  await router.replace("/settings?tab=account");
  await router.replace("/settings?tab=security");
  await vi.waitFor(() =>
    expect(
      document.querySelector('[autocomplete="current-password"]'),
    ).not.toBeNull(),
  );
  expect(
    document.querySelector<HTMLInputElement>(
      '[autocomplete="current-password"]',
    )!.value,
  ).toBe("");
});

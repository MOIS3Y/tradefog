/** Missing allocation is actionable, while transport errors stay retryable. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, type App } from "vue";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import TradeEditor from "@/features/trades/TradeEditor.vue";
import { ApiError } from "@/api/errors";
import { i18n } from "@/i18n";
import { getPlanningContext, type Trade } from "@/features/trades/api";

vi.mock("@/features/trades/api", async (original) => ({
  ...(await original<typeof import("@/features/trades/api")>()),
  getPlanningContext: vi.fn(),
}));
vi.mock("@/features/trades/TradeAttachments.vue", () => ({
  default: { template: "<div />" },
}));

let app: App;
let client: QueryClient;
afterEach(() => {
  app?.unmount();
  client?.clear();
  vi.clearAllMocks();
  document.body.innerHTML = "";
});

const trade: Trade = {
  id: 21,
  profile_id: 3,
  strategy_id: 7,
  instrument_id: 11,
  trade_date: "2026-09-11",
  status: "draft",
  direction: "long",
  description_markdown: null,
  quality_rating: null,
  review_completed_at: null,
  realized_pnl: null,
  actual_exit_price: null,
  total_commission: null,
  funding_result: null,
  submitted_at: null,
  opened_at: null,
  closed_at: null,
  cancelled_at: null,
  created_at: "2026-09-11T12:00:00",
  atr: null,
  snapshot: null,
  plan: null,
  reservations: [],
  checklist: {
    score: "0",
    direction: "NEUTRAL",
    completeness: "0",
    answered_count: 0,
    total_count: 4,
    gauge_position: 50,
    trend_relationship: "UNASSESSED",
    agrees_with_trade: null,
  },
  preparation: {
    planned_entry: "100",
    planned_stop: "90",
    market_sentiment: null,
    information_background: null,
    global_daily_direction: null,
    local_daily_movement: null,
    atr_value: null,
    atr_source: null,
    atr_contributing_date: null,
    atr_observation_time: null,
    atr_stale: false,
    observed_session_range: null,
  },
};

it("links to the selected strategy and keeps inputs on retry", async () => {
  vi.mocked(getPlanningContext).mockRejectedValue(
    new ApiError(409, "settlement_allocation_required", "Missing allocation"),
  );
  document.body.innerHTML = '<div id="root"></div>';
  i18n.global.locale.value = "en";
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/profiles", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  app = createApp(TradeEditor, { trade });
  app
    .use(createPinia())
    .use(i18n)
    .use(router)
    .use(VueQueryPlugin, { queryClient: client })
    .mount("#root");
  await vi.waitFor(() => expect(document.body.textContent).toContain("active"));
  const link = document.querySelector<HTMLAnchorElement>(
    ".position-setup-actions a",
  )!;
  expect(link.getAttribute("href")).toContain(
    "profile=3&tab=strategies&strategy=7",
  );
  expect(link.target).toBe("_blank");
  const actions = document.querySelectorAll(
    ".position-setup-actions .icon-action",
  );
  expect(actions).toHaveLength(3);
  for (const action of actions) {
    expect(action.textContent?.trim()).toBe("");
    expect(action.querySelector("svg")).not.toBeNull();
    expect(action.getAttribute("title")).toBeTruthy();
    expect(action.getAttribute("aria-label")).toBe(
      action.getAttribute("title"),
    );
  }
  expect(getPlanningContext).toHaveBeenCalledTimes(1);
  vi.mocked(getPlanningContext).mockRejectedValue(
    new ApiError(503, "unavailable", "Offline"),
  );
  document
    .querySelector<HTMLButtonElement>(".position-setup-actions button")!
    .click();
  await vi.waitFor(
    () =>
      expect(document.body.textContent).toContain(
        "Position data could not be loaded",
      ),
    { timeout: 5000 },
  );
  expect(document.querySelector(".position-setup-actions a")).toBeNull();
  expect(
    [
      ...document.querySelectorAll<HTMLInputElement>('input[type="number"]'),
    ].some((input) => input.value === "100"),
  ).toBe(true);
});

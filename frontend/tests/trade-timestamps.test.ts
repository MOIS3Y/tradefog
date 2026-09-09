/** Only recorded lifecycle events appear on the trade detail page. */
import { afterEach, expect, it } from "vitest";
import { createApp, h, nextTick, reactive, type App } from "vue";
import { i18n } from "@/i18n";
import TradeTimestamps from "@/features/trades/TradeTimestamps.vue";

let app: App | undefined;
afterEach(() => {
  app?.unmount();
  document.body.innerHTML = "";
});

it("omits absent events and updates when a trade opens", async () => {
  const trade = reactive({
    created_at: "2026-09-09T12:05:07",
    submitted_at: null,
    opened_at: null as string | null,
    closed_at: null,
    cancelled_at: null,
  });
  const root = document.createElement("div");
  document.body.append(root);
  app = createApp({ render: () => h(TradeTimestamps, { trade }) });
  app.use(i18n).mount(root);
  expect(document.querySelectorAll("time")).toHaveLength(1);
  expect(document.querySelector("time")?.dateTime).toBe("2026-09-09T12:05:07Z");
  trade.opened_at = "2026-09-09T12:10:09Z";
  await nextTick();
  expect(document.querySelectorAll("time")).toHaveLength(2);
  expect(document.querySelectorAll("dt")[1]?.textContent).toBe(
    i18n.global.t("tradeTimes.opened_at"),
  );
});

/** Optional pagination visibility without API calls or persisted records. */
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, reactive, type App } from "vue";
import PaginationControls from "@/components/PaginationControls.vue";
import { i18n } from "@/i18n";

let app: App | undefined;

afterEach(() => {
  app?.unmount();
  document.body.innerHTML = "";
});

/** Mount the real component with reactive, in-memory list metadata. */
function mountPagination(
  total: number,
  pageSize = 25,
  hideWhenSmall?: boolean,
) {
  const props = reactive({ page: 1, total, pageSize, hideWhenSmall });
  const shell = document.createElement("div");
  shell.className = "tf-app";
  const root = document.createElement("div");
  shell.append(root);
  document.body.append(shell);
  app = createApp({ render: () => h(PaginationControls, props) });
  app.use(i18n).mount(root);
  return props;
}

describe("optional pagination visibility", () => {
  it.each([0, 1, 24, 25])("hides %i records when enabled", (total) => {
    mountPagination(total, 25, true);
    expect(document.querySelector("nav.pagination")).toBeNull();
  });

  it("shows the first total requiring a second page", () => {
    mountPagination(26, 25, true);
    expect(document.querySelector("nav.pagination")).not.toBeNull();
  });

  it.each([50, 100])("keeps page size %i available to change back", (size) => {
    mountPagination(0, size, true);
    expect(document.querySelector("nav.pagination")).not.toBeNull();
  });

  it.each([undefined, false])("stays visible with option %s", (option) => {
    mountPagination(0, 25, option);
    expect(document.querySelector("nav.pagination")).not.toBeNull();
  });

  it("updates after filtering and returning to the minimum page size", async () => {
    const props = mountPagination(26, 25, true);
    props.total = 25;
    await nextTick();
    expect(document.querySelector("nav.pagination")).toBeNull();
    props.total = 26;
    await nextTick();
    expect(document.querySelector("nav.pagination")).not.toBeNull();
    props.pageSize = 50;
    props.total = 1;
    await nextTick();
    expect(document.querySelector("nav.pagination")).not.toBeNull();
    props.pageSize = 25;
    await nextTick();
    expect(document.querySelector("nav.pagination")).toBeNull();
  });
});

import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useToastStore } from "@/stores/toasts";

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("toast queue", () => {
  it("stacks notifications in arrival order and removes them independently", () => {
    const toasts = useToastStore();
    const successId = toasts.success({ title: "Asset created" });
    const errorId = toasts.error({ title: "Asset was not deleted" });

    expect(toasts.messages.map((message) => message.id)).toEqual([
      successId,
      errorId,
    ]);
    expect(toasts.messages.map((message) => message.duration)).toEqual([
      4_000, 8_000,
    ]);

    toasts.remove(successId);
    expect(toasts.messages).toHaveLength(1);
    expect(toasts.messages[0]?.id).toBe(errorId);
  });
});

/** Event times preserve UTC semantics and local calendar boundaries. */
import { describe, expect, it } from "vitest";
import { formatDateTime, utcTimestamp } from "@/utils/datetime";

describe("trade event dates", () => {
  it("interprets naive API values as UTC without replacing offsets", () => {
    expect(utcTimestamp("2026-09-09T18:05:07")).toBe("2026-09-09T18:05:07Z");
    expect(utcTimestamp("2026-09-09T18:05:07Z")).toBe("2026-09-09T18:05:07Z");
    expect(utcTimestamp("2026-09-09T18:05:07+09:00")).toBe(
      "2026-09-09T18:05:07+09:00",
    );
  });

  it("formats Russian dates with seconds across a local day boundary", () => {
    expect(formatDateTime("2026-09-09T18:05:07", "ru", "Asia/Chita")).toBe(
      "10.09.2026, 03:05:07",
    );
  });

  it("uses 24-hour English times including midnight", () => {
    expect(formatDateTime("2026-09-09T00:00:00Z", "en-US", "UTC")).toBe(
      "09/09/2026, 00:00:00",
    );
    expect(formatDateTime("2026-09-09T09:00:00+09:00", "en-US", "UTC")).toBe(
      "09/09/2026, 00:00:00",
    );
  });
});

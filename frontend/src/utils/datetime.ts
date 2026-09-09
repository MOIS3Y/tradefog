/** Interpret timezone-naive API timestamps as UTC, preserving explicit offsets. */
export function utcTimestamp(value: string): string {
  return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
}

/** Display event timestamps in local time with unambiguous 24-hour precision. */
export function formatDateTime(
  value: string,
  locale: string,
  timeZone?: string,
): string {
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).format(new Date(utcTimestamp(value)));
}

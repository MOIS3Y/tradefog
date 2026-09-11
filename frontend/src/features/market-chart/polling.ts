/** Independent cancellable polling with a shared provider cooldown. */
export class PollingLoop {
  private controller = new AbortController();
  private timer?: ReturnType<typeof setTimeout>;
  private active = false;
  private failures = 0;

  constructor(
    private readonly run: (signal: AbortSignal) => Promise<void>,
    private readonly cooldown: () => number,
    private readonly interval: number,
  ) {}

  get signal(): AbortSignal {
    return this.controller.signal;
  }
  get running(): boolean {
    return this.active;
  }

  /** Abort even when an upstream implementation ignores cancellation. */
  pause(): void {
    this.active = false;
    clearTimeout(this.timer);
    this.controller.abort();
    this.controller = new AbortController();
  }

  /** Resume once without creating a second timer chain. */
  resume(): void {
    if (this.active) return;
    this.active = true;
    this.schedule(0);
  }

  /** Every stream waits after its own completion, never after its sibling. */
  private schedule(delay: number): void {
    if (!this.active) return;
    this.timer = setTimeout(
      () => void this.cycle(),
      Math.max(delay, this.cooldown() - Date.now()),
    );
  }

  /** Recheck a cooldown learned while this timer was waiting. */
  private async cycle(): Promise<void> {
    if (!this.active) return;
    if (Date.now() < this.cooldown()) {
      this.schedule(0);
      return;
    }
    const signal = this.signal;
    try {
      await this.run(signal);
      if (signal.aborted) return;
      this.failures = 0;
    } catch {
      if (signal.aborted) return;
      this.failures = Math.min(this.failures + 1, 4);
    }
    this.schedule(
      this.failures
        ? Math.min(Math.max(this.interval, 5000) * 2 ** this.failures, 60_000)
        : this.interval,
    );
  }
}

/** Protect local form edits during routing and browser navigation. */
import { computed, onBeforeUnmount, readonly, ref, watch, type Ref } from "vue";

const checks = new Set<() => boolean>();
const busyChecks = new Set<() => boolean>();
const pending = ref(false);
let resolveLeave: ((leave: boolean) => void) | undefined;
export const leaveConfirmation = readonly(pending);

/** Complete the single pending route confirmation. */
export function answerLeave(leave: boolean): void {
  pending.value = false;
  resolveLeave?.(leave);
  resolveLeave = undefined;
}

/** Ask once before abandoning any mounted dirty form. */
export function confirmNavigation(): boolean | Promise<boolean> {
  if ([...busyChecks].some((busy) => busy())) return false;
  if (![...checks].some((dirty) => dirty())) return true;
  if (pending.value) return false;
  pending.value = true;
  return new Promise((resolve) => {
    resolveLeave = resolve;
  });
}

/** Block route changes while submitted mutations are still in flight. */
export function useNavigationBusy(count: Ref<number>): void {
  const check = () => count.value > 0;
  busyChecks.add(check);
  onBeforeUnmount(() => busyChecks.delete(check));
}

/** Register a form's comparison with its last saved state. */
export function useLeaveGuard(dirty: Ref<boolean>): void {
  const check = () => dirty.value;
  checks.add(check);
  const beforeUnload = (event: BeforeUnloadEvent) => {
    if (!dirty.value) return;
    event.preventDefault();
    event.returnValue = "";
  };
  window.addEventListener("beforeunload", beforeUnload);
  onBeforeUnmount(() => {
    checks.delete(check);
    window.removeEventListener("beforeunload", beforeUnload);
  });
}

/** Compare an open setup dialog with the values it initially displayed. */
export function useDialogLeaveGuard(
  open: Ref<boolean>,
  values: () => unknown,
): void {
  const initial = ref("");
  watch(open, (visible) => {
    if (visible) initial.value = JSON.stringify(values());
  });
  useLeaveGuard(
    computed(() => open.value && initial.value !== JSON.stringify(values())),
  );
}

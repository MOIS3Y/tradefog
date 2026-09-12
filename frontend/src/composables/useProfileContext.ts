/** URL-owned workspace context; storage is only an entry-point preference. */
import { computed } from "vue";
import { useRoute } from "vue-router";

/** Read a per-account preference without coupling open browser tabs. */
export function readProfileContext(userId: number): number | null {
  try {
    const value = Number(localStorage.getItem(`tradefog.context.${userId}`));
    return Number.isSafeInteger(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

/** Remember only the context, never credentials or server-owned records. */
export function rememberProfileContext(
  userId: number,
  profileId: number | null,
): void {
  try {
    localStorage.setItem(`tradefog.context.${userId}`, String(profileId ?? ""));
  } catch {
    // Navigation also works when browser storage is unavailable.
  }
}

/** Derive the active profile from the current canonical route. */
export function useProfileContext() {
  const route = useRoute();
  const profileId = computed(() => Number(route.params.profileId) || null);
  const prefix = computed(() =>
    profileId.value === null ? "" : `/profiles/${profileId.value}`,
  );
  return { profileId, prefix };
}

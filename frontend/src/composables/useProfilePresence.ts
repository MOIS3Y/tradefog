/** Resolve first-run state without downloading archived profile catalogs. */
import { useQuery } from "@tanstack/vue-query";
import type { ComputedRef } from "vue";
import { listProfilePage } from "@/features/profiles/api";

export function useProfilePresence(enabled: ComputedRef<boolean>) {
  return useQuery({
    queryKey: ["profiles", "presence"],
    queryFn: () =>
      listProfilePage({ visibility: "all", page: 1, page_size: 1 }),
    enabled,
  });
}

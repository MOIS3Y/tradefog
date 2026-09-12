<script setup lang="ts">
import { computed } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import { getAsset, getInstrument } from "@/features/profiles/marketApi";
import { ApiError } from "@/api/errors";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import EmptyState from "@/components/EmptyState.vue";
import { getProfile, listStrategies } from "@/features/profiles/api";
import { getTrade, type Trade } from "@/features/trades/api";
import TradeEditor from "@/features/trades/TradeEditor.vue";

const route = useRoute();
const router = useRouter();
const client = useQueryClient();
const profileId = computed(() => Number(route.params.profileId));
const id = computed(() => Number(route.params.tradeId));
const invalidIdentifier = computed(
  () => !Number.isInteger(id.value) || id.value < 1,
);
const back = computed(() =>
  typeof route.query.returnTo === "string" &&
  /^\/(?:profiles\/\d+\/)?(?:trades|analytics)(?:\?|$)/.test(
    route.query.returnTo,
  )
    ? route.query.returnTo
    : `/profiles/${profileId.value}/trades`,
);
const tradeQuery = useQuery({
  queryKey: computed(() => ["trades", "detail", profileId.value, id.value]),
  queryFn: () => getTrade(profileId.value, id.value),
  enabled: computed(() => Number.isInteger(id.value) && id.value > 0),
});
const trade = computed(() => tradeQuery.data.value);
const profilesQuery = useQuery({
  queryKey: computed(() => ["profiles", "trade-options", profileId.value]),
  queryFn: async () => [await getProfile(profileId.value)],
});
const profiles = computed(() => profilesQuery.data.value ?? []);
const profile = computed(() =>
  profiles.value.find((x) => x.id === trade.value?.profile_id),
);
const strategiesQuery = useQuery({
  queryKey: computed(() => ["profiles", profile.value?.id, "strategies"]),
  queryFn: () => listStrategies(profile.value!.id),
  enabled: computed(() => !!profile.value),
});
const strategy = computed(() =>
  strategiesQuery.data.value?.find((x) => x.id === trade.value?.strategy_id),
);
const instrumentQuery = useQuery({
  queryKey: computed(() => [
    "profile-market",
    trade.value?.profile_id,
    "instrument",
    trade.value?.instrument_id,
  ]),
  enabled: computed(() => !!trade.value),
  queryFn: () =>
    getInstrument(trade.value!.profile_id, trade.value!.instrument_id),
});
const assetsQuery = useQuery({
  queryKey: computed(() => [
    "profile-market",
    profile.value?.id,
    "trade-assets",
    instrumentQuery.data.value?.id,
  ]),
  enabled: computed(() => !!instrumentQuery.data.value && !!profile.value),
  queryFn: async () => {
    const i = instrumentQuery.data.value!;
    return Promise.all([
      getAsset(i.profile_id, i.base_asset_id),
      getAsset(i.profile_id, i.quote_asset_id),
    ]);
  },
});
function updated(value: Trade): void {
  client.setQueryData(["trades", "detail", value.profile_id, value.id], value);
  void client.invalidateQueries({ queryKey: ["trades", "list"] });
  void client.invalidateQueries({ queryKey: ["analytics"] });
  void client.invalidateQueries({ queryKey: ["profiles"] });
}
async function deleted(): Promise<void> {
  client.removeQueries({
    queryKey: ["trades", "detail", profileId.value, id.value],
  });
  await client.invalidateQueries({ queryKey: ["trades", "list"] });
  await router.push(back.value);
}
</script>

<template>
  <RouterLink class="button-link journal-back" :to="back"
    >← {{ $t("journal.back") }}</RouterLink
  >
  <EmptyState
    v-if="
      invalidIdentifier ||
      (tradeQuery.error.value instanceof ApiError &&
        tradeQuery.error.value.status === 404)
    "
    :title="$t('notFound.title')"
    :description="$t('notFound.body')"
  />
  <LoadingState
    v-else-if="
      tradeQuery.isPending.value ||
      profilesQuery.isPending.value ||
      (trade &&
        (instrumentQuery.isPending.value || strategiesQuery.isPending.value))
    "
  />
  <ErrorState
    v-else-if="
      tradeQuery.isError.value ||
      profilesQuery.isError.value ||
      instrumentQuery.isError.value ||
      strategiesQuery.isError.value
    "
    @retry="
      tradeQuery.refetch();
      profilesQuery.refetch();
      instrumentQuery.refetch();
      strategiesQuery.refetch();
    "
  />
  <div v-else-if="trade" class="trade-shell">
    <TradeEditor
      :key="trade.id"
      :trade="trade"
      :profile="profile"
      :strategy="strategy"
      :instrument="instrumentQuery.data.value"
      :base="assetsQuery.data.value?.[0]"
      :quote="assetsQuery.data.value?.[1]"
      @updated="updated"
      @deleted="deleted"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { api } from "@/api/client";
import { ApiError, toApiError } from "@/api/errors";
import AppSelect from "@/components/AppSelect.vue";
import SearchableSelect from "@/components/SearchableSelect.vue";
import RemoteCatalogSelect from "@/components/RemoteCatalogSelect.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import EmptyState from "@/components/EmptyState.vue";
import { listProfiles, listStrategies } from "@/features/profiles/api";
import {
  getTrade,
  createTrade,
  type Trade,
  type Direction,
} from "@/features/trades/api";
import TradeEditor from "@/features/trades/TradeEditor.vue";
import { useToastStore } from "@/stores/toasts";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const client = useQueryClient();
const toasts = useToastStore();
const id = computed(() => Number(route.params.tradeId));
const creating = computed(() => route.path === "/trades/new");
const invalidIdentifier = computed(
  () => !Number.isInteger(id.value) || id.value < 1,
);
const back = computed(() =>
  typeof route.query.returnTo === "string" &&
  /^\/trades(?:\?|$)/.test(route.query.returnTo)
    ? route.query.returnTo
    : "/trades",
);
const tradeQuery = useQuery({
  queryKey: computed(() => ["trades", "detail", id.value]),
  queryFn: () => getTrade(id.value),
  enabled: computed(
    () => !creating.value && Number.isInteger(id.value) && id.value > 0,
  ),
});
const trade = computed(() => tradeQuery.data.value);
const form = reactive({
  profile_id: null as number | null,
  strategy_id: null as number | null,
  venue_instrument_id: null as number | null,
  trade_date: new Date().toISOString().slice(0, 10),
  direction: "long" as Direction,
});
const profilesQuery = useQuery({
  queryKey: ["profiles"],
  queryFn: listProfiles,
});
const profiles = computed(() => profilesQuery.data.value ?? []);
const profile = computed(() =>
  profiles.value.find(
    (x) =>
      x.id === (creating.value ? form.profile_id : trade.value?.profile_id),
  ),
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
    "catalog",
    "instrument",
    trade.value?.venue_instrument_id,
  ]),
  enabled: computed(() => !creating.value && !!trade.value),
  queryFn: async () => {
    const { data, error, response } = await api.GET(
      "/api/v1/catalog/instruments/{instrument_id}",
      { params: { path: { instrument_id: trade.value!.venue_instrument_id } } },
    );
    if (!data) throw toApiError(error, response);
    return data;
  },
});
const profileOptions = computed(() =>
  profiles.value
    .filter((x) => !x.is_archived)
    .map((x) => ({ value: x.id, label: x.name })),
);
const strategyOptions = computed(() =>
  (strategiesQuery.data.value ?? [])
    .filter((x) => !x.is_archived && x.allocations.some((a) => !a.is_archived))
    .map((x) => ({ value: x.id, label: x.name })),
);
const directions = computed(() =>
  (["long", "short"] as const).map((value) => ({
    value,
    label: t(`trades.direction.${value}`),
  })),
);
watch(
  () => form.profile_id,
  () => {
    form.strategy_id = null;
    form.venue_instrument_id = null;
  },
);
const invalid = computed(
  () =>
    !form.profile_id ||
    !form.strategy_id ||
    !form.venue_instrument_id ||
    !form.trade_date,
);
const create = useMutation({
  mutationFn: () =>
    createTrade({
      ...form,
      profile_id: form.profile_id!,
      strategy_id: form.strategy_id!,
      venue_instrument_id: form.venue_instrument_id!,
    }),
  onSuccess: async (value) => {
    client.setQueryData(["trades", "detail", value.id], value);
    await client.invalidateQueries({ queryKey: ["trades", "list"] });
    toasts.success({ title: t("trades.created") });
    await router.replace({
      path: `/trades/${value.id}`,
      query: { returnTo: back.value },
    });
  },
  onError: (error: Error) =>
    toasts.error({
      title: t("trades.createFailed"),
      description: error.message,
    }),
});
function updated(value: Trade): void {
  client.setQueryData(["trades", "detail", value.id], value);
  void client.invalidateQueries({ queryKey: ["trades", "list"] });
}
async function deleted(): Promise<void> {
  client.removeQueries({ queryKey: ["trades", "detail", id.value] });
  await client.invalidateQueries({ queryKey: ["trades", "list"] });
  await router.push(back.value);
}
</script>

<template>
  <RouterLink class="button-link journal-back" :to="back"
    >← {{ $t("journal.back") }}</RouterLink
  >
  <section v-if="creating" class="trade-shell journal-create">
    <h2>{{ $t("trades.createTitle") }}</h2>
    <p>{{ $t("trades.createBody") }}</p>
    <LoadingState v-if="profilesQuery.isPending.value" />
    <ErrorState
      v-else-if="profilesQuery.isError.value"
      @retry="profilesQuery.refetch()"
    />
    <EmptyState
      v-else-if="!profileOptions.length"
      :title="$t('trades.fields.noProfiles')"
      :body="$t('journal.setup')"
      ><RouterLink class="button button--primary" to="/profiles">{{
        $t("trades.fields.profile")
      }}</RouterLink></EmptyState
    >
    <form v-else @submit.prevent="create.mutate()">
      <label class="field"
        ><span>{{ $t("trades.fields.profile") }}</span
        ><SearchableSelect
          v-model="form.profile_id"
          :options="profileOptions"
          :placeholder="$t('trades.fields.selectProfile')"
          :empty-label="$t('trades.fields.noProfiles')"
      /></label>
      <label class="field"
        ><span>{{ $t("trades.fields.strategy") }}</span
        ><SearchableSelect
          v-model="form.strategy_id"
          :options="strategyOptions"
          :disabled="!profile"
          :placeholder="$t('trades.fields.selectStrategy')"
          :empty-label="$t('trades.fields.noStrategies')"
      /></label>
      <ErrorState
        v-if="strategiesQuery.isError.value"
        @retry="strategiesQuery.refetch()"
      />
      <RouterLink
        v-if="
          profile && strategiesQuery.isSuccess.value && !strategyOptions.length
        "
        class="button-link"
        to="/profiles"
        >{{ $t("journal.setup") }}</RouterLink
      >
      <label class="field"
        ><span>{{ $t("trades.fields.instrument") }}</span
        ><RemoteCatalogSelect
          v-model="form.venue_instrument_id"
          resource="instruments"
          :venue-id="profile?.venue_id"
          :params="{ visibility: 'active' }"
          :disabled="!profile"
          :placeholder="$t('trades.fields.selectInstrument')"
          :empty-label="$t('trades.fields.noInstruments')"
      /></label>
      <label class="field"
        ><span>{{ $t("trades.fields.date") }}</span
        ><input v-model="form.trade_date" type="date" required
      /></label>
      <AppSelect
        v-model="form.direction"
        :options="directions"
        :label="$t('journal.allDirections')"
      />
      <div class="journal-create-actions">
        <RouterLink class="button button--secondary" :to="back">{{
          $t("common.cancel")
        }}</RouterLink
        ><button
          class="button button--primary"
          type="submit"
          :disabled="invalid || create.isPending.value"
        >
          {{ $t("trades.createDraft") }}
        </button>
      </div>
    </form>
  </section>
  <template v-else>
    <EmptyState
      v-if="
        invalidIdentifier ||
        (tradeQuery.error.value instanceof ApiError &&
          tradeQuery.error.value.status === 404)
      "
      :title="$t('notFound.title')"
      :body="$t('notFound.body')"
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
        @updated="updated"
        @deleted="deleted"
      />
    </div>
  </template>
</template>

<script setup lang="ts">
/** Create a draft in the journal drawer; position direction belongs to editing. */
import { computed, reactive, watch } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import FormDialog from "@/components/FormDialog.vue";
import SearchableSelect from "@/components/SearchableSelect.vue";
import RemoteCatalogSelect from "@/components/RemoteCatalogSelect.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import EmptyState from "@/components/EmptyState.vue";
import { listProfiles, listStrategies } from "@/features/profiles/api";
import { createTrade } from "./api";
import { useToastStore } from "@/stores/toasts";

const props = defineProps<{ returnTo: string }>();
const emit = defineEmits<{ close: [] }>();
const router = useRouter();
const { t } = useI18n();
const client = useQueryClient();
const toasts = useToastStore();
const form = reactive({
  profile_id: null as number | null,
  strategy_id: null as number | null,
  instrument_id: null as number | null,
  trade_date: new Date().toISOString().slice(0, 10),
});
const profilesQuery = useQuery({
  queryKey: ["profiles"],
  queryFn: listProfiles,
});
const profile = computed(() =>
  profilesQuery.data.value?.find(
    (item) => item.id === form.profile_id && !item.is_archived,
  ),
);
const profileOptions = computed(() =>
  (profilesQuery.data.value ?? [])
    .filter((item) => !item.is_archived)
    .map((item) => ({ value: item.id, label: item.name })),
);
const strategiesQuery = useQuery({
  queryKey: computed(() => ["profiles", profile.value?.id, "strategies"]),
  queryFn: () => listStrategies(profile.value!.id),
  enabled: computed(() => !!profile.value),
});
const strategyOptions = computed(() =>
  (strategiesQuery.data.value ?? [])
    .filter(
      (item) =>
        !item.is_archived &&
        item.allocations.some((allocation) => !allocation.is_archived),
    )
    .map((item) => ({ value: item.id, label: item.name })),
);
watch(
  () => form.profile_id,
  () => {
    form.strategy_id = null;
    form.instrument_id = null;
  },
);
const invalid = computed(
  () =>
    !profile.value ||
    !form.strategy_id ||
    !form.instrument_id ||
    !form.trade_date ||
    !strategyOptions.value.some((item) => item.value === form.strategy_id),
);
const create = useMutation({
  mutationFn: () =>
    createTrade({
      ...form,
      profile_id: form.profile_id!,
      strategy_id: form.strategy_id!,
      instrument_id: form.instrument_id!,
      direction: "long",
    }),
  onSuccess: async (value) => {
    client.setQueryData(["trades", "detail", value.id], value);
    await client.invalidateQueries({ queryKey: ["trades", "list"] });
    toasts.success({ title: t("trades.created") });
    await router.push({
      path: `/trades/${value.id}`,
      query: { returnTo: props.returnTo },
    });
    emit("close");
  },
  onError: (error: Error) =>
    toasts.error({
      title: t("trades.createFailed"),
      description: error.message,
    }),
});
function close(open: boolean): void {
  if (!open && !create.isPending.value) emit("close");
}
function submit(): void {
  if (!invalid.value && !create.isPending.value) create.mutate();
}
</script>

<template>
  <FormDialog
    :open="true"
    :title="$t('trades.createTitle')"
    :description="$t('trades.createBody')"
    :submit-label="$t('trades.createDraft')"
    :cancel-label="$t('common.cancel')"
    :busy="create.isPending.value"
    :invalid="invalid"
    @update:open="close"
    @submit="submit"
  >
    <LoadingState v-if="profilesQuery.isPending.value" />
    <ErrorState
      v-else-if="profilesQuery.isError.value"
      @retry="profilesQuery.refetch()"
    />
    <EmptyState
      v-else-if="!profileOptions.length"
      :title="$t('trades.fields.noProfiles')"
      :description="$t('journal.setup')"
    >
      <RouterLink class="button button--primary" to="/profiles">{{
        $t("trades.fields.profile")
      }}</RouterLink>
    </EmptyState>
    <template v-else>
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
          v-model="form.instrument_id"
          resource="instruments"
          :profile-id="profile?.id"
          :params="{ visibility: 'active' }"
          :disabled="!profile"
          :placeholder="$t('trades.fields.selectInstrument')"
          :empty-label="$t('trades.fields.noInstruments')"
      /></label>
      <label class="field"
        ><span>{{ $t("trades.fields.date") }}</span
        ><input v-model="form.trade_date" type="date" required
      /></label>
    </template>
  </FormDialog>
</template>

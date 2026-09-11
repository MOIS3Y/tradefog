<script setup lang="ts">
import {
  Archive,
  ArchiveRestore,
  Gauge,
  LockKeyhole,
  Pencil,
  Plus,
  ShieldCheck,
  Trash2,
} from "@lucide/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { ApiError } from "@/api/errors";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import SearchableSelect, {
  type SearchableOption,
} from "@/components/SearchableSelect.vue";
import {
  createAllocation,
  createStrategy,
  deleteStrategy,
  getWallet,
  listStrategies,
  updateAllocation,
  updateStrategy,
  type Allocation,
  type Profile,
  type Strategy,
} from "@/features/profiles/api";
import { useToastStore } from "@/stores/toasts";
import {
  compareDecimal,
  formatDecimal,
  isPositiveDecimal,
} from "@/utils/decimal";

const props = defineProps<{ profile: Profile; focusStrategyId?: number }>();
const { t } = useI18n();
const queryClient = useQueryClient();
const toasts = useToastStore();
const selectedId = ref<number | null>(props.focusStrategyId ?? null);
const strategyDialogOpen = ref(false);
const allocationDialogOpen = ref(false);
const editing = ref<Strategy | null>(null);
const allocationEditing = ref<Allocation | null>(null);
const statusTarget = ref<Strategy | null>(null);
const deleteTarget = ref<Strategy | null>(null);
const allocationStatusTarget = ref<Allocation | null>(null);
const strategyForm = reactive({
  name: "",
  description: "",
  riskPercent: "1",
  rewardMultiple: "3",
});
const allocationForm = reactive({
  walletAssetId: null as number | null,
  capital: "",
});

const strategiesKey = computed(() => [
  "profiles",
  props.profile.id,
  "strategies",
]);
const query = useQuery({
  queryKey: strategiesKey,
  queryFn: () => listStrategies(props.profile.id),
});
const walletQuery = useQuery({
  queryKey: computed(() => ["profiles", props.profile.id, "wallet"]),
  queryFn: () => getWallet(props.profile.id),
});
const strategies = computed(() => query.data.value ?? []);
const selected = computed(
  () =>
    strategies.value.find((item) => item.id === selectedId.value) ??
    strategies.value[0] ??
    null,
);
const walletAssets = computed(() => walletQuery.data.value?.assets ?? []);
const walletAssetById = computed(
  () => new Map(walletAssets.value.map((item) => [item.id, item])),
);
const activeAllocations = computed(
  () => selected.value?.allocations.filter((item) => !item.is_archived) ?? [],
);
const availableWalletAssets = computed(() => {
  const assigned = new Set(
    selected.value?.allocations.map((item) => item.asset_id) ?? [],
  );
  return walletAssets.value.filter(
    (item) =>
      !item.is_archived &&
      isPositiveDecimal(item.balance) &&
      !assigned.has(item.id),
  );
});
const walletOptions = computed<SearchableOption[]>(() =>
  (allocationEditing.value
    ? walletAssets.value.filter(
        (item) => item.id === allocationEditing.value?.asset_id,
      )
    : availableWalletAssets.value
  ).map((item) => ({
    value: item.id,
    label: item.symbol,
    detail: `${t("profiles.wallet.balance")}: ${formatDecimal(item.balance)}`,
  })),
);
const strategyInvalid = computed(
  () =>
    strategyForm.name.trim().length === 0 ||
    !positiveDecimal(strategyForm.riskPercent) ||
    compareDecimal(strategyForm.riskPercent, "0.01") < 0 ||
    compareDecimal(strategyForm.riskPercent, "100") > 0 ||
    !/^(?:[3-9]|[1-9]\d|100)$/.test(strategyForm.rewardMultiple),
);
const allocationInvalid = computed(
  () =>
    (!allocationEditing.value && allocationForm.walletAssetId === null) ||
    !positiveDecimal(allocationForm.capital),
);

watch(
  strategies,
  (items) => {
    if (!query.data.value) return;
    if (!items.some((item) => item.id === selectedId.value))
      selectedId.value = items[0]?.id ?? null;
  },
  { immediate: true },
);

function positiveDecimal(value: string): boolean {
  return isPositiveDecimal(value);
}

function showError(error: unknown, title: string): void {
  const apiError = error instanceof ApiError ? error : null;
  const description =
    apiError?.code === "conflict"
      ? t("profiles.strategies.errors.conflict")
      : apiError?.code === "validation_error"
        ? t("catalog.errors.validation")
        : t("catalog.errors.unavailable");
  toasts.error({ title, description });
}

async function refresh(): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: strategiesKey.value }),
    queryClient.invalidateQueries({
      queryKey: ["profiles", props.profile.id, "wallet"],
    }),
  ]);
}

const saveMutation = useMutation({
  mutationFn: () => {
    const input = {
      name: strategyForm.name,
      description: strategyForm.description || null,
      risk_percent: strategyForm.riskPercent,
      reward_multiple: Number(strategyForm.rewardMultiple),
    };
    return editing.value
      ? updateStrategy(props.profile.id, editing.value.id, input)
      : createStrategy(props.profile.id, input);
  },
  onSuccess: async (strategy) => {
    await refresh();
    selectedId.value = strategy.id;
    strategyDialogOpen.value = false;
    toasts.success({
      title: t(
        editing.value
          ? "profiles.strategies.saved"
          : "profiles.strategies.created",
      ),
      description: strategy.name,
    });
  },
  onError: (error) => showError(error, t("profiles.strategies.saveFailed")),
});

const statusMutation = useMutation({
  mutationFn: (strategy: Strategy) =>
    updateStrategy(props.profile.id, strategy.id, {
      is_archived: !strategy.is_archived,
    }),
  onSuccess: async (strategy) => {
    await refresh();
    statusTarget.value = null;
    toasts.success({
      title: t(
        strategy.is_archived
          ? "profiles.strategies.archived"
          : "profiles.strategies.restored",
      ),
      description: strategy.name,
    });
  },
  onError: (error) => showError(error, t("profiles.strategies.saveFailed")),
});

const removeMutation = useMutation({
  mutationFn: (strategy: Strategy) =>
    deleteStrategy(props.profile.id, strategy.id),
  onSuccess: async (_, strategy) => {
    selectedId.value = null;
    await refresh();
    deleteTarget.value = null;
    toasts.success({
      title: t("profiles.strategies.deleted"),
      description: strategy.name,
    });
  },
  onError: (error) => showError(error, t("profiles.strategies.deleteFailed")),
});

const allocationMutation = useMutation({
  mutationFn: () =>
    allocationEditing.value
      ? updateAllocation(
          props.profile.id,
          selected.value!.id,
          allocationEditing.value.id,
          {
            capital: allocationForm.capital,
          },
        )
      : createAllocation(
          props.profile.id,
          selected.value?.id ?? 0,
          allocationForm.walletAssetId ?? 0,
          allocationForm.capital,
        ),
  onSuccess: async () => {
    await refresh();
    allocationDialogOpen.value = false;
    toasts.success({
      title: t(
        allocationEditing.value
          ? "profiles.strategies.allocationSaved"
          : "profiles.strategies.allocationAdded",
      ),
    });
  },
  onError: (error) =>
    showError(error, t("profiles.strategies.allocationFailed")),
});

const allocationStatusMutation = useMutation({
  mutationFn: (allocation: Allocation) =>
    updateAllocation(props.profile.id, selected.value!.id, allocation.id, {
      is_archived: !allocation.is_archived,
    }),
  onSuccess: async () => {
    await refresh();
    allocationStatusTarget.value = null;
    toasts.success({ title: t("profiles.strategies.allocationSaved") });
  },
  onError: (error) =>
    showError(error, t("profiles.strategies.allocationFailed")),
});

function openCreate(): void {
  editing.value = null;
  Object.assign(strategyForm, {
    name: "",
    description: "",
    riskPercent: "1",
    rewardMultiple: "3",
  });
  strategyDialogOpen.value = true;
}

function openEdit(strategy: Strategy): void {
  editing.value = strategy;
  Object.assign(strategyForm, {
    name: strategy.name,
    description: strategy.description ?? "",
    riskPercent: formatDecimal(strategy.risk_percent),
    rewardMultiple: formatDecimal(String(strategy.reward_multiple)),
  });
  strategyDialogOpen.value = true;
}

function openAllocation(allocation: Allocation | null): void {
  allocationEditing.value = allocation;
  Object.assign(allocationForm, {
    walletAssetId: allocation?.asset_id ?? null,
    capital: allocation ? formatDecimal(allocation.capital) : "",
  });
  allocationDialogOpen.value = true;
}
</script>

<template>
  <section class="profile-panel" aria-labelledby="profile-strategies-title">
    <header class="profile-panel__header">
      <div>
        <h4 id="profile-strategies-title">
          <ShieldCheck :size="18" />{{ $t("profiles.strategies.title") }}
        </h4>
        <p>{{ $t("profiles.strategies.description") }}</p>
      </div>
      <button
        class="button button--secondary"
        type="button"
        :disabled="profile.is_archived"
        @click="openCreate"
      >
        <Plus :size="16" />{{ $t("profiles.strategies.create") }}
      </button>
    </header>

    <LoadingState
      v-if="query.isPending.value || walletQuery.isPending.value"
      :label="$t('profiles.strategies.loading')"
    />
    <ErrorState
      v-else-if="query.isError.value || walletQuery.isError.value"
      :title="$t('profiles.strategies.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      :retry-label="$t('common.retry')"
      @retry="
        query.refetch();
        walletQuery.refetch();
      "
    />
    <EmptyState
      v-else-if="strategies.length === 0"
      :title="$t('profiles.strategies.emptyTitle')"
      :description="$t('profiles.strategies.emptyBody')"
    >
      <button
        v-if="!profile.is_archived"
        class="button button--secondary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="16" />{{ $t("profiles.strategies.create") }}
      </button>
    </EmptyState>
    <div v-else class="strategy-layout">
      <div class="strategy-list">
        <button
          v-for="strategy in strategies"
          :key="strategy.id"
          class="strategy-card"
          :class="{
            'strategy-card--selected': strategy.id === selected?.id,
            'strategy-card--archived': strategy.is_archived,
          }"
          type="button"
          @click="selectedId = strategy.id"
        >
          <span class="strategy-card__top"
            ><strong>{{ strategy.name }}</strong
            ><span
              class="health-dot"
              :class="`health-dot--${strategy.status}`"
            ></span
          ></span>
          <span class="strategy-card__rule"
            ><b>{{ formatDecimal(strategy.risk_percent) }}%</b
            ><small>{{ $t("profiles.strategies.riskPerTrade") }}</small></span
          >
          <span class="strategy-card__ratio"
            >1 : {{ formatDecimal(String(strategy.reward_multiple)) }}</span
          >
        </button>
      </div>

      <div v-if="selected" class="strategy-detail">
        <header class="strategy-detail__header">
          <div>
            <span class="section-label">{{
              $t(`profiles.statuses.${selected.status}`)
            }}</span>
            <h5>{{ selected.name }}</h5>
            <p v-if="selected.description">{{ selected.description }}</p>
          </div>
          <div class="profile-detail__actions">
            <button
              class="icon-action"
              type="button"
              :aria-label="$t('catalog.edit')"
              @click="openEdit(selected)"
            >
              <Pencil :size="16" />
            </button>
            <button
              class="icon-action"
              type="button"
              :aria-label="
                $t(
                  selected.is_archived
                    ? 'profiles.restore'
                    : 'profiles.archive',
                )
              "
              @click="statusTarget = selected"
            >
              <ArchiveRestore v-if="selected.is_archived" :size="16" /><Archive
                v-else
                :size="16"
              />
            </button>
            <button
              v-if="selected.is_archived"
              class="icon-action icon-action--danger"
              type="button"
              :aria-label="$t('catalog.delete')"
              @click="deleteTarget = selected"
            >
              <Trash2 :size="16" />
            </button>
          </div>
        </header>
        <div class="strategy-rules">
          <span
            ><Gauge :size="17" /><small>{{
              $t("profiles.strategies.risk")
            }}</small
            ><strong>{{ formatDecimal(selected.risk_percent) }}%</strong></span
          >
          <span
            ><ShieldCheck :size="17" /><small>{{
              $t("profiles.strategies.reward")
            }}</small
            ><strong
              >1 : {{ formatDecimal(String(selected.reward_multiple)) }}</strong
            ></span
          >
        </div>
        <header class="allocation-heading">
          <div>
            <h6>{{ $t("profiles.strategies.allocations") }}</h6>
            <p>{{ $t("profiles.strategies.allocationsBody") }}</p>
          </div>
          <button
            class="button button--secondary"
            type="button"
            :disabled="
              selected.is_archived ||
              profile.is_archived ||
              availableWalletAssets.length === 0
            "
            @click="openAllocation(null)"
          >
            <Plus :size="15" />{{ $t("profiles.strategies.addAllocation") }}
          </button>
        </header>
        <div v-if="selected.allocations.length" class="allocation-list">
          <article
            v-for="allocation in selected.allocations"
            :key="allocation.id"
            class="allocation-row"
            :class="{ 'allocation-row--archived': allocation.is_archived }"
          >
            <span class="allocation-row__symbol">{{
              walletAssetById.get(allocation.asset_id)?.symbol ?? "—"
            }}</span>
            <span
              ><small>{{ $t("profiles.strategies.capital") }}</small
              ><strong>{{ formatDecimal(allocation.capital) }}</strong></span
            >
            <div class="catalog-row-actions">
              <button
                class="icon-action"
                type="button"
                :aria-label="$t('catalog.edit')"
                @click="openAllocation(allocation)"
              >
                <Pencil :size="15" />
              </button>
              <button
                class="icon-action"
                type="button"
                :aria-label="
                  $t(
                    allocation.is_archived
                      ? 'profiles.restore'
                      : 'profiles.archive',
                  )
                "
                @click="allocationStatusTarget = allocation"
              >
                <ArchiveRestore
                  v-if="allocation.is_archived"
                  :size="15"
                /><Archive v-else :size="15" />
              </button>
            </div>
          </article>
        </div>
        <p v-else class="ledger-empty">
          {{
            activeAllocations.length
              ? ""
              : $t("profiles.strategies.noAllocations")
          }}
        </p>
      </div>
    </div>

    <FormDialog
      v-model:open="strategyDialogOpen"
      :title="
        $t(
          editing
            ? 'profiles.strategies.editTitle'
            : 'profiles.strategies.createTitle',
        )
      "
      :description="$t('profiles.strategies.formDescription')"
      :submit-label="
        $t(editing ? 'catalog.saveChanges' : 'profiles.strategies.create')
      "
      :cancel-label="$t('common.cancel')"
      :busy="saveMutation.isPending.value"
      :invalid="strategyInvalid"
      @submit="saveMutation.mutate()"
    >
      <label class="field"
        ><span>{{ $t("profiles.strategies.name") }}</span
        ><input v-model="strategyForm.name" maxlength="128" required
      /></label>
      <div class="form-grid form-grid--two">
        <label class="field"
          ><span>{{ $t("profiles.strategies.risk") }}</span
          ><input
            v-model="strategyForm.riskPercent"
            inputmode="decimal"
            required
          /><small>{{ $t("profiles.strategies.riskHint") }}</small></label
        >
        <label class="field"
          ><span>{{ $t("profiles.strategies.reward") }}</span
          ><input
            v-model="strategyForm.rewardMultiple"
            type="number"
            min="3"
            max="100"
            step="1"
            required
          /><small>{{ $t("profiles.strategies.rewardHint") }}</small></label
        >
      </div>
      <div class="strategy-lock-note">
        <LockKeyhole :size="17" aria-hidden="true" />
        <span>{{ $t("profiles.strategies.rulesLockHint") }}</span>
      </div>
      <label class="field"
        ><span>{{ $t("profiles.strategies.strategyDescription") }}</span
        ><textarea v-model="strategyForm.description" rows="4"></textarea>
      </label>
    </FormDialog>
    <FormDialog
      v-model:open="allocationDialogOpen"
      :title="
        $t(
          allocationEditing
            ? 'profiles.strategies.editAllocation'
            : 'profiles.strategies.addAllocation',
        )
      "
      :description="$t('profiles.strategies.allocationFormBody')"
      :submit-label="
        $t(
          allocationEditing
            ? 'catalog.saveChanges'
            : 'profiles.strategies.addAllocation',
        )
      "
      :cancel-label="$t('common.cancel')"
      :busy="allocationMutation.isPending.value"
      :invalid="allocationInvalid"
      @submit="allocationMutation.mutate()"
    >
      <label class="field"
        ><span>{{ $t("profiles.wallet.asset") }}</span
        ><SearchableSelect
          v-model="allocationForm.walletAssetId"
          :options="walletOptions"
          :placeholder="$t('profiles.strategies.selectWalletAsset')"
          :empty-label="$t('profiles.strategies.noWalletAssets')"
          :disabled="allocationEditing !== null"
      /></label>
      <label class="field"
        ><span>{{ $t("profiles.strategies.capital") }}</span
        ><input
          v-model="allocationForm.capital"
          inputmode="decimal"
          required
        /><small>{{ $t("profiles.strategies.capitalHint") }}</small></label
      >
    </FormDialog>
    <ConfirmDialog
      :open="statusTarget !== null"
      :title="
        $t(
          statusTarget?.is_archived
            ? 'profiles.strategies.restoreTitle'
            : 'profiles.strategies.archiveTitle',
        )
      "
      :description="
        $t(
          statusTarget?.is_archived
            ? 'profiles.strategies.restoreBody'
            : 'profiles.strategies.archiveBody',
          { name: statusTarget?.name },
        )
      "
      :confirm-label="
        $t(statusTarget?.is_archived ? 'profiles.restore' : 'profiles.archive')
      "
      :cancel-label="$t('common.cancel')"
      :busy="statusMutation.isPending.value"
      @update:open="!$event && (statusTarget = null)"
      @confirm="statusTarget && statusMutation.mutate(statusTarget)"
    />
    <ConfirmDialog
      :open="deleteTarget !== null"
      :title="$t('profiles.strategies.deleteTitle')"
      :description="
        $t('profiles.strategies.deleteBody', { name: deleteTarget?.name })
      "
      :confirm-label="$t('catalog.delete')"
      :cancel-label="$t('common.cancel')"
      :busy="removeMutation.isPending.value"
      @update:open="!$event && (deleteTarget = null)"
      @confirm="deleteTarget && removeMutation.mutate(deleteTarget)"
    />
    <ConfirmDialog
      :open="allocationStatusTarget !== null"
      :title="
        $t(
          allocationStatusTarget?.is_archived
            ? 'profiles.strategies.restoreAllocationTitle'
            : 'profiles.strategies.archiveAllocationTitle',
        )
      "
      :description="
        $t(
          allocationStatusTarget?.is_archived
            ? 'profiles.strategies.restoreAllocationBody'
            : 'profiles.strategies.archiveAllocationBody',
        )
      "
      :confirm-label="
        $t(
          allocationStatusTarget?.is_archived
            ? 'profiles.restore'
            : 'profiles.archive',
        )
      "
      :cancel-label="$t('common.cancel')"
      :busy="allocationStatusMutation.isPending.value"
      @update:open="!$event && (allocationStatusTarget = null)"
      @confirm="
        allocationStatusTarget &&
        allocationStatusMutation.mutate(allocationStatusTarget)
      "
    />
  </section>
</template>

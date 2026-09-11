<script setup lang="ts">
import { Search, Coins, Plus } from "@lucide/vue";
import WalletAssetCard from "./WalletAssetCard.vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { ApiError } from "@/api/errors";
import AppSwitch from "@/components/AppSwitch.vue";
import ProfileOperations from "./ProfileOperations.vue";
import PaginationControls from "@/components/PaginationControls.vue";
import { usePagination } from "@/composables/usePagination";
import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import {
  createOperation,
  type Profile,
  type WalletOperationKind,
} from "@/features/profiles/api";
import {
  createAsset,
  updateAsset,
  type Asset,
  listAssets,
  getAsset,
  deleteAsset,
} from "@/features/profiles/marketApi";
import { useToastStore } from "@/stores/toasts";
import { formatDecimal, isPositiveDecimal } from "@/utils/decimal";

const props = defineProps<{ profile: Profile; focusAssetId?: number | null }>();
const { t } = useI18n();
const queryClient = useQueryClient();
const toasts = useToastStore();
const selectedId = ref<number | null>(null);
const assetDialogOpen = ref(false);
const assetEditing = ref<Asset | null>(null);
const operationDialogOpen = ref(false);
const operationTarget = ref<Asset | null>(null);
const pinnedId = ref<number | null>(props.focusAssetId ?? null);
const deleteTarget = ref<Asset | null>(null);
const archiveTarget = ref<Asset | null>(null);
const assetForm = reactive({
  symbol: "",
  name: "",
  asset_type: "crypto" as Asset["asset_type"],
  floor: "",
});
const hideEmpty = ref(true);
const assetSearch = ref("");
const assetType = ref<Asset["asset_type"] | "all">("all");
const typeFilters = computed(() => [
  { value: "all" as const, label: t("profileMarket.allAssetTypes") },
  ...assetTypes.value.filter(
    (item) => props.profile.venue_type !== "bybit" || item.value !== "equity",
  ),
]);
const assetTypes = computed(() =>
  ["crypto", "fiat", "equity"].map((value) => ({
    value: value as Asset["asset_type"],
    label: t(`catalog.types.${value}`),
  })),
);

const operationForm = reactive({
  kind: "deposit" as WalletOperationKind,
  amount: "",
  note: "",
});

const walletKey = computed(() => ["profiles", props.profile.id, "wallet"]);
const assetPagination = usePagination(
  computed(() => ({
    profile: props.profile.id,
    hideEmpty: hideEmpty.value,
    assetType: assetType.value,
    q: assetSearch.value,
  })),
);
const { page: assetPage, pageSize: assetPageSize } = assetPagination;
const walletQuery = useQuery({
  queryKey: computed(() => [
    ...walletKey.value,
    hideEmpty.value,
    assetSearch.value,
    assetType.value,
    assetPagination.params.value,
  ]),
  queryFn: () =>
    listAssets(props.profile.id, {
      ...assetPagination.params.value,
      visibility: "all",
      hide_empty: hideEmpty.value,
      asset_type: assetType.value === "all" ? undefined : assetType.value,
      q: assetSearch.value,
    }),
});
assetPagination.track(computed(() => walletQuery.data.value));
const assets = computed(() => walletQuery.data.value?.items ?? []);
const focusQuery = useQuery({
  queryKey: computed(() => [
    "profiles",
    props.profile.id,
    "asset",
    pinnedId.value,
  ]),
  queryFn: () => getAsset(props.profile.id, pinnedId.value!),
  enabled: computed(
    () =>
      !!pinnedId.value &&
      !assets.value.some((item) => item.id === pinnedId.value),
  ),
});
watch(
  () => props.focusAssetId,
  (id) => {
    if (id) {
      pinnedId.value = id;
      selectedId.value = id;
    }
  },
  { immediate: true },
);
const visibleAssets = computed(() => {
  const focused = focusQuery.data.value;
  return pinnedId.value &&
    focused?.id === pinnedId.value &&
    !assets.value.some((item) => item.id === focused.id)
    ? [focused, ...assets.value]
    : assets.value;
});
const selected = computed(() =>
  walletQuery.isSuccess.value
    ? (visibleAssets.value.find((item) => item.id === selectedId.value) ?? null)
    : null,
);
watch([assetSearch, assetType, hideEmpty, assetPage, assetPageSize], () => {
  pinnedId.value = null;
});
const kindOptions = computed<SelectOption<WalletOperationKind>[]>(() => [
  { value: "deposit", label: t("profiles.wallet.deposit") },
  { value: "withdrawal", label: t("profiles.wallet.withdrawal") },
]);
const assetInvalid = computed(
  () =>
    !assetForm.symbol.trim() ||
    (assetForm.floor !== "" && !/^\d+(\.\d+)?$/.test(assetForm.floor)),
);
const operationInvalid = computed(
  () => !isPositiveDecimal(operationForm.amount),
);

watch(
  visibleAssets,
  (items) => {
    if (!walletQuery.isSuccess.value) return;
    if (pinnedId.value && !items.some((item) => item.id === pinnedId.value))
      return;
    if (!items.some((item) => item.id === selectedId.value)) {
      selectedId.value = items[0]?.id ?? null;
    }
  },
  { immediate: true },
);

function showError(error: unknown, title: string): void {
  const apiError = error instanceof ApiError ? error : null;
  const description =
    apiError?.code === "conflict"
      ? t("profiles.wallet.errors.conflict")
      : apiError?.code === "validation_error"
        ? t("catalog.errors.validation")
        : t("catalog.errors.unavailable");
  toasts.error({ title, description });
}

async function refreshWallet(): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["profiles", props.profile.id] }),
    queryClient.invalidateQueries({
      queryKey: ["profile-market", props.profile.id],
    }),
    queryClient.invalidateQueries({ queryKey: ["profiles", "wallet-assets"] }),
    queryClient.invalidateQueries({
      queryKey: ["profiles", props.profile.id, "strategies"],
    }),
  ]);
}

const addAssetMutation = useMutation({
  mutationFn: () =>
    assetEditing.value
      ? updateAsset(props.profile.id, assetEditing.value.id, {
          name: assetForm.name || null,
          risk_stop_capital: assetForm.floor || null,
        })
      : createAsset(props.profile.id, {
          symbol: assetForm.symbol,
          name: assetForm.name || null,
          asset_type: assetForm.asset_type,
        }),
  onSuccess: async (asset) => {
    hideEmpty.value = false;
    await refreshWallet();
    pinnedId.value = asset.id;
    selectedId.value = asset.id;
    assetDialogOpen.value = false;
    toasts.success({
      title: t(
        assetEditing.value
          ? "profiles.wallet.assetSaved"
          : "profiles.wallet.assetAdded",
      ),
      description: asset.symbol,
    });
  },
  onError: (error) => showError(error, t("profiles.wallet.saveFailed")),
});

const assetStatusMutation = useMutation({
  mutationFn: (asset: Asset) =>
    updateAsset(props.profile.id, asset.id, {
      is_archived: !asset.is_archived,
    }),
  onSuccess: async (asset) => {
    await refreshWallet();
    archiveTarget.value = null;
    toasts.success({
      title: t(
        asset.is_archived
          ? "profiles.wallet.assetArchived"
          : "profiles.wallet.assetRestored",
      ),
      description: asset.symbol,
    });
  },
  onError: (error) => showError(error, t("profiles.wallet.saveFailed")),
});

const deleteMutation = useMutation({
  mutationFn: (asset: Asset) => deleteAsset(props.profile.id, asset.id),
  onSuccess: async () => {
    if (pinnedId.value === deleteTarget.value?.id) pinnedId.value = null;
    selectedId.value = null;
    deleteTarget.value = null;
    await refreshWallet();
  },
  onError: (error) => showError(error, t("profiles.wallet.saveFailed")),
});

const operationMutation = useMutation({
  mutationFn: () =>
    createOperation(props.profile.id, operationTarget.value!.id, {
      kind: operationForm.kind,
      amount: operationForm.amount,
      note: operationForm.note || null,
    }),
  onSuccess: async () => {
    await refreshWallet();
    operationDialogOpen.value = false;
    toasts.success({ title: t("profiles.wallet.operationAdded") });
  },
  onError: (error) => showError(error, t("profiles.wallet.operationFailed")),
});

function openAssetDialog(asset: Asset | null = null): void {
  assetEditing.value = asset;
  Object.assign(assetForm, {
    symbol: asset?.symbol ?? "",
    name: asset?.name ?? "",
    asset_type: asset?.asset_type ?? "crypto",
    floor: asset?.risk_stop_capital
      ? formatDecimal(asset.risk_stop_capital)
      : "",
  });
  assetDialogOpen.value = true;
}

function openOperationDialog(asset: Asset): void {
  operationTarget.value = asset;
  selectedId.value = asset.id;
  Object.assign(operationForm, { kind: "deposit", amount: "", note: "" });
  operationDialogOpen.value = true;
}
</script>

<template>
  <section class="profile-panel" aria-labelledby="profile-wallet-title">
    <header class="profile-panel__header">
      <div>
        <h4 id="profile-wallet-title">
          <Coins :size="18" />{{ $t("profiles.wallet.title") }}
        </h4>
        <p>{{ $t("profiles.wallet.description") }}</p>
      </div>
      <button
        v-if="profile.venue_type === 'manual'"
        class="button button--secondary"
        type="button"
        :disabled="profile.is_archived"
        @click="openAssetDialog()"
      >
        <Plus :size="16" />
        {{ $t("profiles.wallet.addAsset") }}
      </button>
    </header>

    <div class="profile-toolbar">
      <label class="search-field">
        <Search class="search-field__icon" :size="16" aria-hidden="true" />
        <input
          v-model="assetSearch"
          type="search"
          :aria-label="$t('profileMarket.searchAssets')"
          :placeholder="$t('profileMarket.searchAssets')"
        />
      </label>
      <AppSelect
        v-model="assetType"
        :options="typeFilters"
        :label="$t('profileMarket.assetTypes')"
      />
      <AppSwitch v-model="hideEmpty" :label="$t('profileMarket.hideEmpty')" />
    </div>
    <LoadingState
      v-if="walletQuery.isPending.value"
      :label="$t('profiles.wallet.loading')"
    />
    <ErrorState
      v-else-if="walletQuery.isError.value"
      :title="$t('profiles.wallet.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      :retry-label="$t('common.retry')"
      @retry="walletQuery.refetch()"
    />
    <EmptyState
      v-else-if="visibleAssets.length === 0 && !pinnedId"
      :title="$t('profiles.wallet.emptyTitle')"
      :description="
        $t(
          profile.venue_type === 'bybit'
            ? 'profileMarket.bybitWalletHelp'
            : 'profiles.wallet.emptyBody',
        )
      "
    >
      <button
        v-if="!profile.is_archived && profile.venue_type === 'manual'"
        class="button button--secondary"
        type="button"
        @click="openAssetDialog()"
      >
        <Plus :size="16" />{{ $t("profiles.wallet.addAsset") }}
      </button>
    </EmptyState>
    <div v-else class="wallet-layout">
      <div class="wallet-assets">
        <WalletAssetCard
          v-for="asset in visibleAssets"
          :key="asset.id"
          :asset="asset"
          :selected="asset.id === selected?.id"
          :archived-profile="profile.is_archived"
          @select="selectedId = asset.id"
          @edit="openAssetDialog(asset)"
          @operation="openOperationDialog(asset)"
          @archive="archiveTarget = asset"
          @delete="deleteTarget = asset"
        />
      </div>

      <PaginationControls
        v-model:page="assetPage"
        v-model:page-size="assetPageSize"
        :total="walletQuery.data.value?.total ?? 0"
        :busy="walletQuery.isFetching.value"
      />
    </div>
    <LoadingState v-if="pinnedId && focusQuery.isPending.value && !selected" />
    <ErrorState
      v-else-if="pinnedId && focusQuery.isError.value"
      @retry="focusQuery.refetch()"
    />
    <ProfileOperations
      :key="profile.id"
      :profile-id="profile.id"
      :asset-id="selected?.id ?? null"
      :asset-symbol="selected?.symbol ?? ''"
    />

    <FormDialog
      v-model:open="assetDialogOpen"
      :title="
        $t(
          assetEditing
            ? 'profiles.wallet.editAssetTitle'
            : 'profiles.wallet.addAssetTitle',
        )
      "
      :description="$t('profiles.wallet.addAssetBody')"
      :submit-label="
        $t(assetEditing ? 'catalog.saveChanges' : 'profiles.wallet.addAsset')
      "
      :cancel-label="$t('common.cancel')"
      :busy="addAssetMutation.isPending.value"
      :invalid="assetInvalid"
      @submit="addAssetMutation.mutate()"
    >
      <label class="field"
        ><span>{{ $t("profileMarket.symbol") }}</span>
        <input
          v-model="assetForm.symbol"
          maxlength="32"
          :disabled="!!assetEditing"
        />
      </label>
      <label class="field"
        ><span>{{ $t("profileMarket.name") }}</span>
        <input v-model="assetForm.name" maxlength="255" />
      </label>
      <AppSelect
        v-if="!assetEditing"
        v-model="assetForm.asset_type"
        :options="assetTypes"
        :label="$t('profileMarket.assetType')"
      />
      <label v-if="assetEditing" class="field"
        ><span>{{ $t("profiles.wallet.riskFloor") }}</span
        ><input
          v-model="assetForm.floor"
          inputmode="decimal"
          placeholder="0.00"
        /><small>{{ $t("profiles.wallet.riskFloorHint") }}</small></label
      >
    </FormDialog>
    <FormDialog
      v-model:open="operationDialogOpen"
      :title="
        $t('profiles.wallet.addOperationTitle') +
        ' · ' +
        (operationTarget?.symbol ?? '')
      "
      :description="$t('profiles.wallet.operationImmutable')"
      :submit-label="$t('profiles.wallet.addOperation')"
      :cancel-label="$t('common.cancel')"
      :busy="operationMutation.isPending.value"
      :invalid="operationInvalid"
      @submit="operationMutation.mutate()"
    >
      <label class="field"
        ><span>{{ $t("profiles.wallet.operationType") }}</span
        ><AppSelect
          v-model="operationForm.kind"
          :options="kindOptions"
          :label="$t('profiles.wallet.operationType')"
      /></label>
      <label class="field"
        ><span>{{ $t("profiles.wallet.amount") }}</span
        ><input
          v-model="operationForm.amount"
          inputmode="decimal"
          required
          placeholder="0.00"
      /></label>
      <label class="field"
        ><span>{{ $t("profiles.wallet.note") }}</span
        ><textarea
          v-model="operationForm.note"
          maxlength="255"
          rows="3"
        ></textarea>
      </label>
    </FormDialog>
    <ConfirmDialog
      :open="!!deleteTarget"
      :title="$t('catalog.delete')"
      :description="$t('profileMarket.deleteHelp')"
      :confirm-label="$t('catalog.delete')"
      :cancel-label="$t('common.cancel')"
      :busy="deleteMutation.isPending.value"
      @update:open="!$event && (deleteTarget = null)"
      @confirm="deleteTarget && deleteMutation.mutate(deleteTarget)"
    />
    <ConfirmDialog
      :open="archiveTarget !== null"
      :title="
        $t(
          archiveTarget?.is_archived
            ? 'profiles.wallet.restoreAssetTitle'
            : 'profiles.wallet.archiveAssetTitle',
        )
      "
      :description="
        $t(
          archiveTarget?.is_archived
            ? 'profiles.wallet.restoreAssetBody'
            : 'profiles.wallet.archiveAssetBody',
          { symbol: archiveTarget?.symbol },
        )
      "
      :confirm-label="
        $t(
          archiveTarget?.is_archived
            ? 'profiles.wallet.restoreAsset'
            : 'profiles.wallet.archiveAsset',
        )
      "
      :cancel-label="$t('common.cancel')"
      :busy="assetStatusMutation.isPending.value"
      @update:open="!$event && (archiveTarget = null)"
      @confirm="archiveTarget && assetStatusMutation.mutate(archiveTarget)"
    />
  </section>
</template>

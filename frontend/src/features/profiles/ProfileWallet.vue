<script setup lang="ts">
import {
  Archive,
  ArchiveRestore,
  ArrowDownLeft,
  ArrowUpRight,
  Coins,
  Pencil,
  Plus,
} from "@lucide/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import RemoteCatalogSelect from "@/components/RemoteCatalogSelect.vue";
import { ApiError } from "@/api/errors";
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
  createWalletAsset,
  getWallet,
  listOperations,
  updateOperationNote,
  updateWalletAsset,
  type Profile,
  type WalletAsset,
  type WalletOperation,
  type WalletOperationKind,
} from "@/features/profiles/api";
import { listAssets } from "@/features/profiles/marketApi";
import { useToastStore } from "@/stores/toasts";
import { formatDecimal, isPositiveDecimal } from "@/utils/decimal";

const props = defineProps<{ profile: Profile }>();
const { t, locale } = useI18n();
const queryClient = useQueryClient();
const toasts = useToastStore();
const selectedId = ref<number | null>(null);
const assetDialogOpen = ref(false);
const assetEditing = ref<WalletAsset | null>(null);
const operationDialogOpen = ref(false);
const noteDialogOpen = ref(false);
const archiveTarget = ref<WalletAsset | null>(null);
const operationTarget = ref<WalletOperation | null>(null);
const assetForm = reactive({ capabilityId: null as number | null, floor: "" });
const operationForm = reactive({
  kind: "deposit" as WalletOperationKind,
  amount: "",
  note: "",
});
const note = ref("");

const walletKey = computed(() => ["profiles", props.profile.id, "wallet"]);
const walletQuery = useQuery({
  queryKey: walletKey,
  queryFn: () => getWallet(props.profile.id),
});
const capabilitiesQuery = useQuery({
  queryKey: computed(() => [
    "profile-market",
    props.profile.id,
    "assets",
    "wallet-options",
  ]),
  queryFn: () =>
    listAssets(props.profile.id, { visibility: "active", page_size: 1 }),
});
const assets = computed(() => walletQuery.data.value?.assets ?? []);
const selected = computed(
  () =>
    assets.value.find((item) => item.id === selectedId.value) ??
    assets.value[0] ??
    null,
);
const availableCapabilities = computed(
  () => capabilitiesQuery.data.value?.items ?? [],
);
const capabilityParams = computed(() => ({
  visibility: "active" as const,
  excludeIds: assetEditing.value ? [] : assets.value.map((x) => x.asset_id),
}));
const operationsKey = computed(() => [
  "profiles",
  "wallet-assets",
  props.profile.id,
  "operations",
]);
const operationPagination = usePagination(computed(() => props.profile.id));
const { page: operationPage, pageSize: operationPageSize } =
  operationPagination;
const operationsQuery = useQuery({
  queryKey: computed(() => [
    ...operationsKey.value,
    operationPagination.params.value,
  ]),
  queryFn: () =>
    listOperations(props.profile.id, operationPagination.params.value),
  enabled: computed(() => selected.value !== null),
});
operationPagination.track(computed(() => operationsQuery.data.value));
const operations = computed(() => operationsQuery.data.value?.items ?? []);
const kindOptions = computed<SelectOption<WalletOperationKind>[]>(() => [
  { value: "deposit", label: t("profiles.wallet.deposit") },
  { value: "withdrawal", label: t("profiles.wallet.withdrawal") },
]);
const assetInvalid = computed(
  () =>
    assetForm.capabilityId === null ||
    (assetForm.floor !== "" && !/^\d+(\.\d+)?$/.test(assetForm.floor)),
);
const operationInvalid = computed(
  () => !isPositiveDecimal(operationForm.amount),
);

watch(
  assets,
  (items) => {
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
    queryClient.invalidateQueries({ queryKey: walletKey.value }),
    queryClient.invalidateQueries({ queryKey: ["profiles", "wallet-assets"] }),
    queryClient.invalidateQueries({
      queryKey: ["profiles", props.profile.id, "strategies"],
    }),
  ]);
}

const addAssetMutation = useMutation({
  mutationFn: () =>
    assetEditing.value
      ? updateWalletAsset(props.profile.id, assetEditing.value.id, {
          risk_stop_capital: assetForm.floor || null,
        })
      : createWalletAsset(props.profile.id, {
          asset_id: assetForm.capabilityId ?? 0,
          risk_stop_capital: assetForm.floor || null,
        }),
  onSuccess: async (asset) => {
    await refreshWallet();
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
  mutationFn: (asset: WalletAsset) =>
    updateWalletAsset(props.profile.id, asset.id, {
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

const operationMutation = useMutation({
  mutationFn: () =>
    createOperation(props.profile.id, {
      wallet_asset_id: selected.value!.id,
      kind: operationForm.kind,
      amount: operationForm.amount,
      note: operationForm.note || null,
    }),
  onSuccess: async () => {
    operationPage.value = 1;
    await refreshWallet();
    operationDialogOpen.value = false;
    toasts.success({ title: t("profiles.wallet.operationAdded") });
  },
  onError: (error) => showError(error, t("profiles.wallet.operationFailed")),
});

const noteMutation = useMutation({
  mutationFn: () =>
    updateOperationNote(
      props.profile.id,
      operationTarget.value?.id ?? 0,
      note.value || null,
    ),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: operationsKey.value });
    noteDialogOpen.value = false;
    toasts.success({ title: t("profiles.wallet.noteSaved") });
  },
  onError: (error) => showError(error, t("profiles.wallet.noteFailed")),
});

function openAssetDialog(asset: WalletAsset | null = null): void {
  assetEditing.value = asset;
  Object.assign(assetForm, {
    capabilityId: asset?.asset_id ?? null,
    floor: asset?.risk_stop_capital
      ? formatDecimal(asset.risk_stop_capital)
      : "",
  });
  assetDialogOpen.value = true;
}

function openOperationDialog(): void {
  Object.assign(operationForm, { kind: "deposit", amount: "", note: "" });
  operationDialogOpen.value = true;
}

function openNoteDialog(operation: WalletOperation): void {
  operationTarget.value = operation;
  note.value = operation.note ?? "";
  noteDialogOpen.value = true;
}

function formattedDate(value: string): string {
  const utcValue = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`;
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(utcValue));
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
        class="button button--secondary"
        type="button"
        :disabled="profile.is_archived || availableCapabilities.length === 0"
        @click="openAssetDialog()"
      >
        <Plus :size="16" />
        {{
          availableCapabilities.length
            ? $t("profiles.wallet.addAsset")
            : $t("profiles.wallet.noAssetsAvailable")
        }}
      </button>
    </header>

    <LoadingState
      v-if="walletQuery.isPending.value || capabilitiesQuery.isPending.value"
      :label="$t('profiles.wallet.loading')"
    />
    <ErrorState
      v-else-if="walletQuery.isError.value || capabilitiesQuery.isError.value"
      :title="$t('profiles.wallet.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      :retry-label="$t('common.retry')"
      @retry="
        walletQuery.refetch();
        capabilitiesQuery.refetch();
      "
    />
    <EmptyState
      v-else-if="assets.length === 0"
      :title="$t('profiles.wallet.emptyTitle')"
      :description="$t('profiles.wallet.emptyBody')"
    >
      <button
        v-if="!profile.is_archived && availableCapabilities.length"
        class="button button--secondary"
        type="button"
        @click="openAssetDialog()"
      >
        <Plus :size="16" />{{ $t("profiles.wallet.addAsset") }}
      </button>
    </EmptyState>
    <div v-else class="wallet-layout">
      <div class="wallet-assets">
        <button
          v-for="asset in assets"
          :key="asset.id"
          class="wallet-balance-card"
          :class="{
            'wallet-balance-card--selected': asset.id === selected?.id,
            'wallet-balance-card--archived': asset.is_archived,
          }"
          type="button"
          @click="selectedId = asset.id"
        >
          <span class="wallet-balance-card__heading">
            <strong>{{ asset.symbol }}</strong>
            <span
              class="health-dot"
              :class="`health-dot--${asset.status}`"
            ></span>
          </span>
          <span class="wallet-balance-card__balance">{{
            formatDecimal(asset.balance)
          }}</span>
          <span class="wallet-balance-card__metrics">
            <small
              >{{ $t("profiles.wallet.available") }}
              <b>{{ formatDecimal(asset.available) }}</b></small
            >
            <small
              >{{ $t("profiles.wallet.allocated") }}
              <b>{{ formatDecimal(asset.allocated) }}</b></small
            >
          </span>
        </button>
      </div>

      <div v-if="selected" class="ledger-panel">
        <header class="ledger-panel__header">
          <div>
            <span class="section-label">{{ selected.symbol }}</span>
            <h5>{{ $t("profileMarket.ledger") }}</h5>
          </div>
          <div class="profile-detail__actions">
            <button
              class="icon-action"
              type="button"
              :aria-label="$t('catalog.edit')"
              @click="openAssetDialog(selected)"
            >
              <Pencil :size="16" />
            </button>
            <button
              class="icon-action"
              type="button"
              :aria-label="
                $t(
                  selected.is_archived
                    ? 'profiles.wallet.restoreAsset'
                    : 'profiles.wallet.archiveAsset',
                )
              "
              @click="archiveTarget = selected"
            >
              <ArchiveRestore v-if="selected.is_archived" :size="16" />
              <Archive v-else :size="16" />
            </button>
            <button
              class="button button--secondary"
              type="button"
              :disabled="profile.is_archived || selected.is_archived"
              @click="openOperationDialog"
            >
              <Plus :size="15" />{{ $t("profiles.wallet.addOperation") }}
            </button>
          </div>
        </header>
        <div class="wallet-summary">
          <span
            ><small>{{ $t("profiles.wallet.balance") }}</small
            ><strong
              >{{ formatDecimal(selected.balance) }}
              {{ selected.symbol }}</strong
            ></span
          >
          <span
            ><small>{{ $t("profiles.wallet.reserved") }}</small
            ><strong>{{ formatDecimal(selected.reserved) }}</strong></span
          >
          <span
            ><small>{{ $t("profiles.wallet.uncommitted") }}</small
            ><strong>{{ formatDecimal(selected.uncommitted) }}</strong></span
          >
          <span
            ><small>{{ $t("profiles.wallet.riskFloor") }}</small
            ><strong>{{
              selected.risk_stop_capital
                ? formatDecimal(selected.risk_stop_capital)
                : "—"
            }}</strong></span
          >
        </div>
        <LoadingState
          v-if="operationsQuery.isPending.value"
          :label="$t('profiles.wallet.loadingOperations')"
        />
        <ErrorState
          v-else-if="operationsQuery.isError.value"
          @retry="operationsQuery.refetch()"
        />
        <div v-else-if="operations.length" class="ledger-list">
          <article
            v-for="operation in operations"
            :key="operation.id"
            class="ledger-row"
          >
            <span
              class="ledger-row__icon"
              :class="`ledger-row__icon--${operation.kind}`"
            >
              <ArrowDownLeft v-if="operation.kind === 'deposit'" :size="16" />
              <ArrowUpRight v-else :size="16" />
            </span>
            <span class="ledger-row__main">
              <strong>{{ $t(`profiles.wallet.${operation.kind}`) }}</strong>
              <small>{{ formattedDate(operation.created_at) }}</small>
            </span>
            <span class="ledger-row__note">{{
              operation.note || $t("profiles.wallet.noNote")
            }}</span>
            <strong
              class="ledger-row__amount"
              :class="`ledger-row__amount--${operation.kind}`"
            >
              {{ operation.kind === "deposit" ? "+" : ""
              }}{{ formatDecimal(operation.amount) }}
              {{
                assets.find((asset) => asset.id === operation.wallet_asset_id)
                  ?.symbol
              }}
            </strong>
            <button
              class="icon-action"
              type="button"
              :aria-label="$t('profiles.wallet.editNote')"
              @click="openNoteDialog(operation)"
            >
              <Pencil :size="15" />
            </button>
          </article>
        </div>
        <p v-else class="ledger-empty">
          {{ $t("profiles.wallet.noOperations") }}
        </p>
        <PaginationControls
          v-if="operationsQuery.isSuccess.value"
          v-model:page="operationPage"
          v-model:page-size="operationPageSize"
          :total="operationsQuery.data.value?.total ?? 0"
          :busy="operationsQuery.isFetching.value"
        />
      </div>
    </div>

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
        ><span>{{ $t("profiles.wallet.asset") }}</span
        ><RemoteCatalogSelect
          v-model="assetForm.capabilityId"
          resource="assets"
          :profile-id="profile.id"
          :params="{ visibility: 'active' }"
          :exclude-ids="capabilityParams.excludeIds"
          :placeholder="$t('profiles.wallet.selectAsset')"
          :empty-label="$t('profiles.wallet.noAssetsAvailable')"
          :disabled="assetEditing !== null"
      /></label>
      <label class="field"
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
      :title="$t('profiles.wallet.addOperationTitle')"
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
    <FormDialog
      v-model:open="noteDialogOpen"
      :title="$t('profiles.wallet.editNote')"
      :description="$t('profiles.wallet.noteOnly')"
      :submit-label="$t('catalog.saveChanges')"
      :cancel-label="$t('common.cancel')"
      :busy="noteMutation.isPending.value"
      @submit="noteMutation.mutate()"
    >
      <label class="field"
        ><span>{{ $t("profiles.wallet.note") }}</span
        ><textarea v-model="note" maxlength="255" rows="4"></textarea>
      </label>
    </FormDialog>
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

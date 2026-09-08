<script setup lang="ts">
import {
  Archive,
  ArchiveRestore,
  Building2,
  ExternalLink,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "@lucide/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { ApiError } from "@/api/errors";
import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import {
  createVenue,
  deleteVenue,
  listVenues,
  updateVenue,
  type MarketDataProvider,
  type Venue,
  type VenueWrite,
} from "@/features/venues/api";
import { filterVenues, type VisibilityFilter } from "@/features/venues/filters";
import VenueInstruments from "@/features/venues/VenueInstruments.vue";
import VenueWalletAssets from "@/features/venues/VenueWalletAssets.vue";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toasts";

type VenueTab = "instruments" | "wallet";

const auth = useAuthStore();
const toasts = useToastStore();
const queryClient = useQueryClient();
const { t } = useI18n();

const search = ref("");
const visibility = ref<VisibilityFilter>("active");
const selectedId = ref<number | null>(null);
const activeTab = ref<VenueTab>("instruments");
const dialogOpen = ref(false);
const editing = ref<Venue | null>(null);
const statusTarget = ref<Venue | null>(null);
const deleteTarget = ref<Venue | null>(null);
const form = reactive<VenueWrite>({
  name: "",
  market_data_provider: "none",
  description: null,
  website: null,
  is_active: true,
});

const query = useQuery({
  queryKey: ["catalog", "venues"],
  queryFn: listVenues,
});
const venues = computed(() => query.data.value ?? []);
const filtered = computed(() =>
  filterVenues(venues.value, search.value, visibility.value).sort((a, b) =>
    a.name.localeCompare(b.name),
  ),
);
const selected = computed(
  () => venues.value.find((venue) => venue.id === selectedId.value) ?? null,
);
const formInvalid = computed(() => form.name.trim().length === 0);
const visibilityOptions = computed<SelectOption<VisibilityFilter>[]>(() => [
  { value: "active", label: t("venues.visibility.active") },
  { value: "archived", label: t("venues.visibility.archived") },
  { value: "all", label: t("venues.visibility.all") },
]);
const providerOptions = computed<SelectOption<MarketDataProvider>[]>(() => [
  { value: "none", label: t("venues.providers.none") },
  { value: "bybit", label: t("venues.providers.bybit") },
  { value: "binance", label: t("venues.providers.binance") },
  { value: "yfinance", label: t("venues.providers.yfinance") },
]);

watch(
  filtered,
  (items) => {
    if (!items.some((venue) => venue.id === selectedId.value)) {
      selectedId.value = items[0]?.id ?? null;
    }
  },
  { immediate: true },
);

function showError(error: unknown, action: "save" | "delete"): void {
  const apiError = error instanceof ApiError ? error : null;
  const description =
    apiError?.code === "venue_in_use"
      ? t("venues.errors.inUse")
      : apiError?.code === "venue_not_archived"
        ? t("venues.errors.notArchived")
        : apiError?.code === "validation_error"
          ? t("catalog.errors.validation")
          : apiError?.code === "conflict"
            ? t("venues.errors.conflict")
            : t("catalog.errors.unavailable");
  toasts.error({
    title: t(action === "save" ? "venues.saveFailed" : "venues.deleteFailed"),
    description,
  });
}

const saveMutation = useMutation({
  mutationFn: () =>
    editing.value === null
      ? createVenue(form)
      : updateVenue(editing.value.id, {
          name: form.name,
          market_data_provider: form.market_data_provider,
          description: form.description,
          website: form.website,
        }),
  onSuccess: async (venue) => {
    await queryClient.invalidateQueries({ queryKey: ["catalog", "venues"] });
    selectedId.value = venue.id;
    toasts.success({
      title: t(editing.value === null ? "venues.created" : "venues.saved"),
    });
    dialogOpen.value = false;
  },
  onError: (error) => showError(error, "save"),
});

const statusMutation = useMutation({
  mutationFn: (venue: Venue) =>
    updateVenue(venue.id, { is_active: !venue.is_active }),
  onSuccess: async (venue) => {
    await queryClient.invalidateQueries({ queryKey: ["catalog", "venues"] });
    toasts.success({
      title: t(venue.is_active ? "venues.restored" : "venues.archived"),
      description: venue.name,
    });
    statusTarget.value = null;
  },
  onError: (error) => showError(error, "save"),
});

const removeMutation = useMutation({
  mutationFn: (venue: Venue) => deleteVenue(venue.id),
  onSuccess: async (_, venue) => {
    selectedId.value = null;
    await queryClient.invalidateQueries({ queryKey: ["catalog", "venues"] });
    toasts.success({
      title: t("venues.deleted"),
      description: venue.name,
    });
    deleteTarget.value = null;
  },
  onError: (error) => showError(error, "delete"),
});

function openCreate(): void {
  editing.value = null;
  Object.assign(form, {
    name: "",
    market_data_provider: "none",
    description: null,
    website: null,
    is_active: true,
  });
  dialogOpen.value = true;
}

function openEdit(venue: Venue): void {
  editing.value = venue;
  Object.assign(form, {
    name: venue.name,
    market_data_provider: venue.market_data_provider,
    description: venue.description,
    website: venue.website,
    is_active: venue.is_active,
  });
  dialogOpen.value = true;
}

function resetFilters(): void {
  search.value = "";
  visibility.value = "active";
}

function websiteHref(website: string): string {
  return /^https?:\/\//i.test(website) ? website : `https://${website}`;
}
</script>

<template>
  <section
    class="catalog-section venue-workspace"
    aria-labelledby="venues-title"
  >
    <header class="catalog-section__header">
      <div>
        <h2 id="venues-title" class="catalog-section__title">
          <Building2 :size="21" aria-hidden="true" />
          {{ $t("venues.title") }}
        </h2>
        <p class="catalog-section__description">
          {{ $t("venues.description") }}
        </p>
      </div>
      <button
        v-if="auth.user?.is_staff"
        class="button button--primary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="17" aria-hidden="true" />
        {{ $t("venues.create") }}
      </button>
    </header>

    <div class="catalog-toolbar venue-toolbar" role="search">
      <label class="search-field">
        <span class="sr-only">{{ $t("venues.search") }}</span>
        <Search class="search-field__icon" :size="16" aria-hidden="true" />
        <input
          v-model="search"
          type="search"
          :placeholder="$t('venues.search')"
        />
      </label>
      <AppSelect
        v-model="visibility"
        :options="visibilityOptions"
        :label="$t('venues.status')"
      />
      <button
        v-if="search || visibility !== 'active'"
        class="button-link"
        type="button"
        @click="resetFilters"
      >
        {{ $t("catalog.reset") }}
      </button>
      <span class="catalog-toolbar__count">
        {{ filtered.length }} / {{ venues.length }}
      </span>
    </div>

    <LoadingState v-if="query.isPending.value" :label="$t('venues.loading')" />
    <ErrorState
      v-else-if="query.isError.value"
      :title="$t('catalog.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      @retry="query.refetch()"
    />
    <EmptyState
      v-else-if="venues.length === 0"
      :title="$t('venues.emptyTitle')"
    >
      <template #icon><Building2 :size="24" /></template>
      <button
        v-if="auth.user?.is_staff"
        class="button button--primary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="17" aria-hidden="true" />
        {{ $t("venues.createFirst") }}
      </button>
    </EmptyState>
    <div v-else-if="filtered.length === 0" class="catalog-no-results">
      <Search :size="22" aria-hidden="true" />
      <p>{{ $t("catalog.noResults") }}</p>
      <button class="button-link" type="button" @click="resetFilters">
        {{ $t("catalog.reset") }}
      </button>
    </div>

    <div v-else class="venue-console">
      <aside class="venue-directory" :aria-label="$t('venues.title')">
        <button
          v-for="venue in filtered"
          :key="venue.id"
          :class="[
            'venue-card',
            { 'venue-card--selected': venue.id === selectedId },
          ]"
          type="button"
          :aria-pressed="venue.id === selectedId"
          @click="selectedId = venue.id"
        >
          <span class="venue-card__mark">{{ venue.name.slice(0, 2) }}</span>
          <span class="venue-card__copy">
            <strong>{{ venue.name }}</strong>
            <small>{{
              $t(`venues.providers.${venue.market_data_provider}`)
            }}</small>
          </span>
          <span
            :class="[
              'status-dot',
              { 'status-dot--archived': !venue.is_active },
            ]"
            :title="
              $t(venue.is_active ? 'venues.active' : 'venues.archivedState')
            "
          ></span>
          <span class="sr-only">
            {{ $t(venue.is_active ? "venues.active" : "venues.archivedState") }}
          </span>
        </button>
      </aside>

      <article v-if="selected" class="venue-detail">
        <header class="venue-detail__header">
          <div class="venue-detail__identity">
            <span class="venue-provider">
              {{ $t(`venues.providers.${selected.market_data_provider}`) }}
            </span>
            <div class="venue-detail__title-row">
              <h3>{{ selected.name }}</h3>
              <span
                :class="[
                  'catalog-tag',
                  selected.is_active
                    ? 'catalog-tag--active'
                    : 'catalog-tag--archived',
                ]"
              >
                {{
                  $t(
                    selected.is_active
                      ? "venues.active"
                      : "venues.archivedState",
                  )
                }}
              </span>
            </div>
            <p v-if="selected.description">{{ selected.description }}</p>
            <a
              v-if="selected.website"
              class="venue-website"
              :href="websiteHref(selected.website)"
              target="_blank"
              rel="noreferrer"
            >
              {{ selected.website }}
              <ExternalLink :size="13" aria-hidden="true" />
            </a>
          </div>
          <div v-if="auth.user?.is_staff" class="venue-detail__actions">
            <button
              class="icon-action"
              type="button"
              :aria-label="$t('catalog.edit')"
              @click="openEdit(selected)"
            >
              <Pencil :size="16" aria-hidden="true" />
            </button>
            <button
              class="icon-action"
              type="button"
              :aria-label="
                $t(selected.is_active ? 'venues.archive' : 'venues.restore')
              "
              @click="statusTarget = selected"
            >
              <Archive
                v-if="selected.is_active"
                :size="16"
                aria-hidden="true"
              />
              <ArchiveRestore v-else :size="16" aria-hidden="true" />
            </button>
            <button
              v-if="!selected.is_active"
              class="icon-action icon-action--danger"
              type="button"
              :aria-label="$t('catalog.delete')"
              @click="deleteTarget = selected"
            >
              <Trash2 :size="16" aria-hidden="true" />
            </button>
          </div>
        </header>

        <nav
          class="venue-tabs"
          role="tablist"
          :aria-label="$t('venues.sections')"
        >
          <button
            :class="{
              'venue-tabs__button--active': activeTab === 'instruments',
            }"
            type="button"
            role="tab"
            :aria-selected="activeTab === 'instruments'"
            @click="activeTab = 'instruments'"
          >
            {{ $t("venues.instruments.title") }}
          </button>
          <button
            :class="{ 'venue-tabs__button--active': activeTab === 'wallet' }"
            type="button"
            role="tab"
            :aria-selected="activeTab === 'wallet'"
            @click="activeTab = 'wallet'"
          >
            {{ $t("venues.walletAssets.title") }}
          </button>
        </nav>

        <VenueInstruments
          v-if="activeTab === 'instruments'"
          :venue="selected"
        />
        <VenueWalletAssets v-else :venue="selected" />
      </article>
    </div>

    <FormDialog
      v-model:open="dialogOpen"
      :title="$t(editing ? 'venues.editTitle' : 'venues.createTitle')"
      :description="$t('venues.formDescription')"
      :submit-label="$t(editing ? 'catalog.saveChanges' : 'venues.create')"
      :cancel-label="$t('common.cancel')"
      :busy="saveMutation.isPending.value"
      :invalid="formInvalid"
      @submit="saveMutation.mutate()"
    >
      <label class="field">
        <span>{{ $t("venues.name") }}</span>
        <input
          v-model="form.name"
          maxlength="128"
          autocomplete="off"
          placeholder="Bybit"
          required
        />
      </label>
      <label class="field">
        <span>{{ $t("venues.provider") }}</span>
        <AppSelect
          v-model="form.market_data_provider"
          :options="providerOptions"
          :label="$t('venues.provider')"
        />
        <small>{{ $t("venues.providerHint") }}</small>
      </label>
      <label class="field">
        <span>{{ $t("venues.website") }}</span>
        <input
          v-model="form.website"
          maxlength="255"
          autocomplete="url"
          placeholder="https://www.bybit.com"
        />
      </label>
      <label class="field">
        <span>{{ $t("venues.venueDescription") }}</span>
        <textarea
          v-model="form.description"
          rows="4"
          :placeholder="$t('venues.descriptionPlaceholder')"
        ></textarea>
      </label>
    </FormDialog>

    <ConfirmDialog
      :open="statusTarget !== null"
      :title="
        $t(
          statusTarget?.is_active
            ? 'venues.archiveTitle'
            : 'venues.restoreTitle',
        )
      "
      :description="
        $t(
          statusTarget?.is_active ? 'venues.archiveBody' : 'venues.restoreBody',
          { name: statusTarget?.name },
        )
      "
      :confirm-label="
        $t(statusTarget?.is_active ? 'venues.archive' : 'venues.restore')
      "
      :cancel-label="$t('common.cancel')"
      :busy="statusMutation.isPending.value"
      @update:open="!$event && (statusTarget = null)"
      @confirm="statusTarget && statusMutation.mutate(statusTarget)"
    />

    <ConfirmDialog
      :open="deleteTarget !== null"
      :title="$t('venues.deleteTitle')"
      :description="$t('venues.deleteBody', { name: deleteTarget?.name })"
      :confirm-label="$t('catalog.delete')"
      :cancel-label="$t('common.cancel')"
      :busy="removeMutation.isPending.value"
      @update:open="!$event && (deleteTarget = null)"
      @confirm="deleteTarget && removeMutation.mutate(deleteTarget)"
    />
  </section>
</template>

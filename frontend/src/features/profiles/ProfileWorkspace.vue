<script setup lang="ts">
import {
  Archive,
  ArchiveRestore,
  BriefcaseBusiness,
  Landmark,
  Pencil,
  Plus,
  Search,
  Trash2,
  WalletCards,
} from "@lucide/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/errors";
import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import SearchableSelect, {
  type SearchableOption,
} from "@/components/SearchableSelect.vue";
import ProfileStrategies from "@/features/profiles/ProfileStrategies.vue";
import ProfileWallet from "@/features/profiles/ProfileWallet.vue";
import {
  createProfile,
  deleteProfile,
  listProfiles,
  updateProfile,
  type Profile,
} from "@/features/profiles/api";
import { listVenues } from "@/features/venues/api";
import { useToastStore } from "@/stores/toasts";

type ProfileTab = "wallet" | "strategies";
type Visibility = "active" | "archived" | "all";

const { t } = useI18n();
const router = useRouter();
const queryClient = useQueryClient();
const toasts = useToastStore();
const search = ref("");
const visibility = ref<Visibility>("active");
const selectedId = ref<number | null>(null);
const activeTab = ref<ProfileTab>("wallet");
const dialogOpen = ref(false);
const editing = ref<Profile | null>(null);
const statusTarget = ref<Profile | null>(null);
const deleteTarget = ref<Profile | null>(null);
const form = reactive({
  venue_id: null as number | null,
  name: "",
  description: "",
});

const profilesQuery = useQuery({
  queryKey: ["profiles"],
  queryFn: listProfiles,
});
const venuesQuery = useQuery({
  queryKey: ["catalog", "venues"],
  queryFn: listVenues,
});
const profiles = computed(() => profilesQuery.data.value ?? []);
const venues = computed(() => venuesQuery.data.value ?? []);
const activeVenues = computed(() =>
  venues.value.filter((item) => item.is_active),
);
const venueById = computed(
  () => new Map(venues.value.map((item) => [item.id, item])),
);
const venueOptions = computed<SearchableOption[]>(() =>
  activeVenues.value.map((venue) => ({
    value: venue.id,
    label: venue.name,
    detail: t(`venues.providers.${venue.market_data_provider}`),
  })),
);
const visibilityOptions = computed<SelectOption<Visibility>[]>(() => [
  { value: "active", label: t("profiles.visibility.active") },
  { value: "archived", label: t("profiles.visibility.archived") },
  { value: "all", label: t("profiles.visibility.all") },
]);
const filtered = computed(() => {
  const needle = search.value.trim().toLocaleLowerCase();
  return profiles.value
    .filter((profile) => {
      const visible =
        visibility.value === "all" ||
        (visibility.value === "archived"
          ? profile.is_archived
          : !profile.is_archived);
      const venue = venueById.value.get(profile.venue_id)?.name ?? "";
      return (
        visible &&
        `${profile.name} ${venue}`.toLocaleLowerCase().includes(needle)
      );
    })
    .sort((left, right) => left.name.localeCompare(right.name));
});
const selected = computed(
  () => profiles.value.find((item) => item.id === selectedId.value) ?? null,
);
const formInvalid = computed(
  () => form.name.trim().length === 0 || form.venue_id === null,
);

watch(
  filtered,
  (items) => {
    if (!items.some((item) => item.id === selectedId.value)) {
      selectedId.value = items[0]?.id ?? null;
    }
  },
  { immediate: true },
);

function reportError(error: unknown, title: string): void {
  const apiError = error instanceof ApiError ? error : null;
  const description =
    apiError?.code === "invalid_venue"
      ? t("profiles.errors.invalidVenue")
      : apiError?.code === "conflict"
        ? t("profiles.errors.conflict")
        : t("catalog.errors.unavailable");
  toasts.error({ title, description });
}

const saveMutation = useMutation({
  mutationFn: () =>
    editing.value === null
      ? createProfile({
          venue_id: form.venue_id ?? 0,
          name: form.name,
          description: form.description || null,
        })
      : updateProfile(editing.value.id, {
          name: form.name,
          description: form.description || null,
        }),
  onSuccess: async (profile) => {
    await queryClient.invalidateQueries({ queryKey: ["profiles"] });
    selectedId.value = profile.id;
    dialogOpen.value = false;
    toasts.success({
      title: t(editing.value === null ? "profiles.created" : "profiles.saved"),
      description: profile.name,
    });
  },
  onError: (error) => reportError(error, t("profiles.saveFailed")),
});

const statusMutation = useMutation({
  mutationFn: (profile: Profile) =>
    updateProfile(profile.id, { is_archived: !profile.is_archived }),
  onSuccess: async (profile) => {
    visibility.value = profile.is_archived ? "archived" : "active";
    selectedId.value = profile.id;
    await queryClient.invalidateQueries({ queryKey: ["profiles"] });
    statusTarget.value = null;
    toasts.success({
      title: t(profile.is_archived ? "profiles.archived" : "profiles.restored"),
      description: profile.name,
    });
  },
  onError: (error) => reportError(error, t("profiles.saveFailed")),
});

const removeMutation = useMutation({
  mutationFn: (profile: Profile) => deleteProfile(profile.id),
  onSuccess: async (_, profile) => {
    selectedId.value = null;
    await queryClient.invalidateQueries({ queryKey: ["profiles"] });
    deleteTarget.value = null;
    toasts.success({ title: t("profiles.deleted"), description: profile.name });
  },
  onError: (error) => reportError(error, t("profiles.deleteFailed")),
});

function openCreate(): void {
  if (activeVenues.value.length === 0) {
    void router.push("/catalog/venues");
    return;
  }
  editing.value = null;
  Object.assign(form, { venue_id: null, name: "", description: "" });
  dialogOpen.value = true;
}

function openEdit(profile: Profile): void {
  editing.value = profile;
  Object.assign(form, {
    venue_id: profile.venue_id,
    name: profile.name,
    description: profile.description ?? "",
  });
  dialogOpen.value = true;
}
</script>

<template>
  <section class="profile-shell" aria-labelledby="profiles-heading">
    <header class="catalog-section__header">
      <div>
        <h2 id="profiles-heading" class="catalog-section__title">
          <BriefcaseBusiness :size="21" aria-hidden="true" />
          {{ $t("profiles.heading") }}
        </h2>
        <p class="catalog-section__description">
          {{ $t("profiles.description") }}
        </p>
      </div>
      <button class="button button--primary" type="button" @click="openCreate">
        <Plus :size="17" aria-hidden="true" />
        {{
          activeVenues.length ? $t("profiles.create") : $t("profiles.addVenue")
        }}
      </button>
    </header>

    <div class="profile-toolbar" role="search">
      <label class="search-field">
        <span class="sr-only">{{ $t("profiles.search") }}</span>
        <Search class="search-field__icon" :size="16" aria-hidden="true" />
        <input
          v-model="search"
          type="search"
          :placeholder="$t('profiles.search')"
        />
      </label>
      <AppSelect
        v-model="visibility"
        :options="visibilityOptions"
        :label="$t('profiles.status')"
      />
    </div>

    <LoadingState
      v-if="profilesQuery.isPending.value || venuesQuery.isPending.value"
      :label="$t('profiles.loading')"
    />
    <ErrorState
      v-else-if="profilesQuery.isError.value || venuesQuery.isError.value"
      :title="$t('profiles.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      :retry-label="$t('common.retry')"
      @retry="
        profilesQuery.refetch();
        venuesQuery.refetch();
      "
    />
    <EmptyState
      v-else-if="profiles.length === 0"
      :title="$t('profiles.emptyTitle')"
      :description="
        activeVenues.length
          ? $t('profiles.emptyBody')
          : $t('profiles.noVenueBody')
      "
    >
      <button
        class="button button--secondary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="16" />
        {{
          activeVenues.length ? $t("profiles.create") : $t("profiles.addVenue")
        }}
      </button>
    </EmptyState>
    <div v-else class="profile-console">
      <aside class="profile-directory" :aria-label="$t('profiles.heading')">
        <button
          v-for="profile in filtered"
          :key="profile.id"
          class="profile-card"
          :class="{ 'profile-card--selected': profile.id === selectedId }"
          type="button"
          @click="selectedId = profile.id"
        >
          <span class="profile-card__mark"><Landmark :size="17" /></span>
          <span class="profile-card__copy">
            <strong>{{ profile.name }}</strong>
            <small>{{ venueById.get(profile.venue_id)?.name }}</small>
          </span>
          <span
            class="status-dot"
            :class="{ 'status-dot--archived': profile.is_archived }"
          ></span>
        </button>
        <p v-if="filtered.length === 0" class="profile-directory__empty">
          {{ $t("catalog.noResults") }}
        </p>
      </aside>

      <div v-if="selected" class="profile-detail">
        <header class="profile-detail__header">
          <div>
            <span class="profile-detail__venue">{{
              venueById.get(selected.venue_id)?.name
            }}</span>
            <div class="profile-detail__title-row">
              <h3>{{ selected.name }}</h3>
              <span
                class="catalog-tag"
                :class="
                  selected.is_archived
                    ? 'catalog-tag--archived'
                    : 'catalog-tag--active'
                "
              >
                {{
                  $t(
                    selected.is_archived
                      ? "profiles.archivedState"
                      : "profiles.active",
                  )
                }}
              </span>
            </div>
            <p v-if="selected.description">{{ selected.description }}</p>
          </div>
          <div class="profile-detail__actions">
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
                $t(
                  selected.is_archived
                    ? 'profiles.restore'
                    : 'profiles.archive',
                )
              "
              @click="statusTarget = selected"
            >
              <ArchiveRestore v-if="selected.is_archived" :size="16" />
              <Archive v-else :size="16" />
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
        <nav class="profile-tabs" :aria-label="$t('profiles.sections')">
          <button
            type="button"
            :class="{ 'profile-tabs__button--active': activeTab === 'wallet' }"
            @click="activeTab = 'wallet'"
          >
            <WalletCards :size="16" />{{ $t("profiles.wallet.tab") }}
          </button>
          <button
            type="button"
            :class="{
              'profile-tabs__button--active': activeTab === 'strategies',
            }"
            @click="activeTab = 'strategies'"
          >
            <BriefcaseBusiness :size="16" />{{ $t("profiles.strategies.tab") }}
          </button>
        </nav>
        <ProfileWallet v-if="activeTab === 'wallet'" :profile="selected" />
        <ProfileStrategies v-else :profile="selected" />
      </div>
    </div>

    <FormDialog
      v-model:open="dialogOpen"
      :title="$t(editing ? 'profiles.editTitle' : 'profiles.createTitle')"
      :description="$t('profiles.formDescription')"
      :submit-label="$t(editing ? 'catalog.saveChanges' : 'profiles.create')"
      :cancel-label="$t('common.cancel')"
      :busy="saveMutation.isPending.value"
      :invalid="formInvalid"
      @submit="saveMutation.mutate()"
    >
      <label class="field">
        <span>{{ $t("profiles.name") }}</span>
        <input v-model="form.name" maxlength="128" required />
      </label>
      <label class="field">
        <span>{{ $t("profiles.venue") }}</span>
        <SearchableSelect
          v-model="form.venue_id"
          :options="venueOptions"
          :placeholder="$t('profiles.selectVenue')"
          :empty-label="$t('profiles.noVenues')"
          :disabled="editing !== null"
        />
        <small>{{
          editing ? $t("profiles.venueLocked") : $t("profiles.venueHint")
        }}</small>
      </label>
      <label class="field">
        <span>{{ $t("profiles.profileDescription") }}</span>
        <textarea v-model="form.description" rows="4"></textarea>
      </label>
    </FormDialog>

    <ConfirmDialog
      :open="statusTarget !== null"
      :title="
        $t(
          statusTarget?.is_archived
            ? 'profiles.restoreTitle'
            : 'profiles.archiveTitle',
        )
      "
      :description="
        $t(
          statusTarget?.is_archived
            ? 'profiles.restoreBody'
            : 'profiles.archiveBody',
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
      :title="$t('profiles.deleteTitle')"
      :description="$t('profiles.deleteBody', { name: deleteTarget?.name })"
      :confirm-label="$t('catalog.delete')"
      :cancel-label="$t('common.cancel')"
      :busy="removeMutation.isPending.value"
      @update:open="!$event && (deleteTarget = null)"
      @confirm="deleteTarget && removeMutation.mutate(deleteTarget)"
    />
  </section>
</template>

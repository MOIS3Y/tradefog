<script setup lang="ts">
import { useDialogLeaveGuard } from "@/composables/useLeaveGuard";
import {
  Archive,
  ExternalLink,
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
import { useRoute, useRouter } from "vue-router";

import { useProfilePresence } from "@/composables/useProfilePresence";
import ProfileDirectoryCard from "@/features/profiles/ProfileDirectoryCard.vue";
import ProfileMarket from "@/features/profiles/ProfileMarket.vue";
import { ApiError } from "@/api/errors";
import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import PanelHeading from "@/components/PanelHeading.vue";
import PaginationControls from "@/components/PaginationControls.vue";
import { usePagination } from "@/composables/usePagination";
import ProfileStrategies from "@/features/profiles/ProfileStrategies.vue";
import ProfileWallet from "@/features/profiles/ProfileWallet.vue";
import {
  createProfile,
  deleteProfile,
  listProfilePage,
  getProfile,
  updateProfile,
  type Profile,
} from "@/features/profiles/api";
import { listVenues, type VenueType } from "@/features/profiles/marketApi";
import { useToastStore } from "@/stores/toasts";

type ProfileTab = "market" | "wallet" | "strategies";
type Visibility = "active" | "archived" | "all";

const { t } = useI18n();

const queryClient = useQueryClient();
const toasts = useToastStore();
const search = ref("");
const visibility = ref<Visibility>("active");
const route = useRoute();
const router = useRouter();
const scoped = computed(() => !!route.params.profileId);
const requestedProfile = Number(route.params.profileId);
const selectedId = ref<number | null>(
  Number.isSafeInteger(requestedProfile) && requestedProfile > 0
    ? requestedProfile
    : null,
);
const activeTab = ref<ProfileTab>(
  route.params.section === "wallet" || route.params.section === "strategies"
    ? route.params.section
    : "market",
);
const requestedAsset = Number(route.query.asset);
const focusAssetId = ref<number | null>(
  Number.isSafeInteger(requestedAsset) && requestedAsset > 0
    ? requestedAsset
    : null,
);
watch(selectedId, () => {
  focusAssetId.value = null;
});
/** Keep setup sections addressable and shared with the global switcher. */
function selectTab(tab: ProfileTab): void {
  if (selectedId.value)
    void router.push({
      path: `/profiles/${selectedId.value}/${tab}`,
      query: focusAssetId.value ? { asset: focusAssetId.value } : {},
    });
}
const dialogOpen = ref(false);
const editing = ref<Profile | null>(null);
const statusTarget = ref<Profile | null>(null);
const deleteTarget = ref<Profile | null>(null);
const form = reactive({
  venue_type: "bybit" as VenueType,
  venue_url: "",
  name: "",
  description: "",
});

const criteria = computed(() => ({
  q: search.value,
  visibility: visibility.value,
  sort: "name",
}));
const pagination = usePagination(criteria);
const { page, pageSize } = pagination;
const profilesQuery = useQuery({
  queryKey: computed(() => [
    "profiles",
    "list",
    requestedProfile || "overview",
    criteria.value,
    pagination.params.value,
  ]),
  queryFn: async () =>
    scoped.value
      ? {
          items: [await getProfile(requestedProfile)],
          total: 1,
          page: 1,
          page_size: 25,
        }
      : listProfilePage({ ...criteria.value, ...pagination.params.value }),
});
pagination.track(computed(() => profilesQuery.data.value));
const needsPresence = computed(
  () =>
    profilesQuery.isSuccess.value &&
    profilesQuery.data.value?.total === 0 &&
    (visibility.value !== "all" || !!search.value.trim()),
);
const presence = useProfilePresence(needsPresence);
const firstProfile = computed(
  () =>
    !search.value.trim() &&
    visibility.value !== "archived" &&
    (needsPresence.value
      ? presence.data.value?.total === 0
      : profilesQuery.data.value?.total === 0),
);
function showAllProfiles(): void {
  search.value = "";
  visibility.value = "all";
  page.value = 1;
}
const venuesQuery = useQuery({
  queryKey: ["venue-capabilities"],
  queryFn: listVenues,
});
const profiles = computed(() => profilesQuery.data.value?.items ?? []);
const selectedQuery = useQuery({
  queryKey: computed(() => ["profiles", "detail", selectedId.value]),
  queryFn: () => getProfile(selectedId.value!),
  enabled: computed(
    () =>
      selectedId.value !== null &&
      !profiles.value.some((item) => item.id === selectedId.value),
  ),
});
const selected = computed(
  () =>
    profiles.value.find((item) => item.id === selectedId.value) ??
    selectedQuery.data.value ??
    null,
);
const venueOptions = computed(() =>
  (venuesQuery.data.value ?? []).map((v) => ({
    value: v.code as VenueType,
    label: v.code === "manual" ? t("profileMarket.manual") : v.name,
  })),
);
const visibilityOptions = computed<SelectOption<Visibility>[]>(() => [
  { value: "active", label: t("profiles.visibility.active") },
  { value: "archived", label: t("profiles.visibility.archived") },
  { value: "all", label: t("profiles.visibility.all") },
]);
const filtered = profiles;
const formInvalid = computed(
  () => form.name.trim().length === 0 || !form.venue_type,
);

watch(
  filtered,
  (items) => {
    if (scoped.value || !profilesQuery.data.value) return;
    if (
      selectedId.value !== requestedProfile &&
      !items.some((item) => item.id === selectedId.value)
    ) {
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
          venue_type: form.venue_type,
          name: form.name,
          description: form.description || null,
          venue_url: form.venue_url.trim() || null,
        })
      : updateProfile(editing.value.id, {
          name: form.name,
          description: form.description || null,
          venue_url: form.venue_url.trim() || null,
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
  editing.value = null;
  Object.assign(form, {
    venue_type: "bybit",
    venue_url: "",
    name: "",
    description: "",
  });
  dialogOpen.value = true;
}

function openEdit(profile: Profile): void {
  editing.value = profile;
  Object.assign(form, {
    venue_type: profile.venue_type,
    venue_url: profile.venue_url ?? "",
    name: profile.name,
    description: profile.description ?? "",
  });
  dialogOpen.value = true;
}
/** Enter a newly created profile after its write has completed. */
async function saveProfile(): Promise<void> {
  const creating = editing.value === null;
  try {
    const profile = await saveMutation.mutateAsync();
    if (creating) await router.push(`/profiles/${profile.id}/market`);
  } catch {
    // The mutation preserves the form and reports the failure.
  }
}

/** Leave a deleted profile only after the mutation releases navigation. */
async function removeProfile(): Promise<void> {
  if (!deleteTarget.value) return;
  try {
    await removeMutation.mutateAsync(deleteTarget.value);
    if (scoped.value) await router.push("/trades");
  } catch {
    // The mutation reports why this profile could not be removed.
  }
}

useDialogLeaveGuard(dialogOpen, () => form);
</script>

<template>
  <section class="profile-shell" :aria-label="$t('profiles.title')">
    <PanelHeading
      embedded
      :icon="BriefcaseBusiness"
      :title="$t('profiles.title')"
      :description="$t('profiles.description')"
    >
      <button class="button button--primary" type="button" @click="openCreate">
        <Plus :size="17" aria-hidden="true" />
        {{ $t("profiles.create") }}
      </button>
    </PanelHeading>

    <div v-if="!scoped" class="profile-toolbar" role="search">
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

    <ErrorState
      v-if="scoped && selectedQuery.isError.value"
      :description="selectedQuery.error.value?.message"
      @retry="selectedQuery.refetch()"
    />
    <LoadingState
      v-else-if="
        (scoped && selectedQuery.isPending.value && !selected) ||
        profilesQuery.isPending.value ||
        venuesQuery.isPending.value ||
        (needsPresence && presence.isPending.value)
      "
      :label="$t('profiles.loading')"
    />
    <ErrorState
      v-else-if="
        profilesQuery.isError.value ||
        venuesQuery.isError.value ||
        (needsPresence && presence.isError.value)
      "
      :title="$t('profiles.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      :retry-label="$t('common.retry')"
      @retry="
        profilesQuery.refetch();
        venuesQuery.refetch();
        if (needsPresence) presence.refetch();
      "
    />
    <EmptyState
      v-else-if="profilesQuery.data.value?.total === 0"
      :title="
        $t(
          firstProfile
            ? 'workspaceEmpty.profiles.title'
            : 'workspaceEmpty.filteredProfiles.title',
        )
      "
      :description="
        $t(
          firstProfile
            ? 'workspaceEmpty.profiles.description'
            : 'workspaceEmpty.filteredProfiles.description',
        )
      "
    >
      <button
        class="button button--secondary"
        type="button"
        @click="firstProfile ? openCreate() : showAllProfiles()"
      >
        <Plus v-if="firstProfile" :size="16" />
        {{
          $t(
            firstProfile
              ? "profiles.create"
              : "workspaceEmpty.filteredProfiles.action",
          )
        }}
      </button>
    </EmptyState>
    <div
      v-else
      class="profile-console"
      :class="{ 'profile-console--directory': !scoped }"
      :style="{ gridTemplateColumns: '1fr' }"
    >
      <aside
        v-if="!scoped"
        class="profile-directory"
        :aria-label="$t('profiles.heading')"
      >
        <div class="profile-directory__items">
          <ProfileDirectoryCard
            v-for="profile in filtered"
            :key="profile.id"
            :profile="profile"
          />
          <p v-if="filtered.length === 0" class="profile-directory__empty">
            {{ $t("catalog.noResults") }}
          </p>
        </div>
        <PaginationControls
          hide-when-small
          v-model:page="page"
          v-model:page-size="pageSize"
          compact
          :total="profilesQuery.data.value?.total ?? 0"
          :busy="profilesQuery.isFetching.value"
        />
      </aside>

      <div v-if="selected && scoped" class="profile-detail">
        <header class="profile-detail__header">
          <div>
            <span class="profile-detail__venue">{{
              selected.venue_type === "bybit"
                ? "Bybit"
                : $t("profileMarket.manual")
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
            <a
              v-if="selected.venue_url"
              :href="selected.venue_url"
              class="icon-action"
              target="_blank"
              rel="noopener noreferrer"
              :aria-label="$t('profileMarket.openVenue')"
              :title="$t('profileMarket.openVenue')"
            >
              <ExternalLink :size="16"
            /></a>
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
            :class="{ 'profile-tabs__button--active': activeTab === 'market' }"
            @click="selectTab('market')"
          >
            <Landmark :size="16" />{{ $t("profiles.venue") }}
          </button>
          <button
            type="button"
            :class="{ 'profile-tabs__button--active': activeTab === 'wallet' }"
            @click="selectTab('wallet')"
          >
            <WalletCards :size="16" />{{ $t("profiles.wallet.tab") }}
          </button>
          <button
            type="button"
            :class="{
              'profile-tabs__button--active': activeTab === 'strategies',
            }"
            @click="selectTab('strategies')"
          >
            <BriefcaseBusiness :size="16" />{{ $t("profiles.strategies.tab") }}
          </button>
        </nav>
        <ProfileMarket
          v-if="activeTab === 'market'"
          @fund="
            focusAssetId = $event;
            selectTab('wallet');
          "
          :key="selected.id"
          :profile="selected"
        />
        <ProfileWallet
          v-else-if="activeTab === 'wallet'"
          :focus-asset-id="focusAssetId"
          :key="selected.id"
          :profile="selected"
        />
        <ProfileStrategies
          v-else
          :key="selected.id"
          :profile="selected"
          :focus-strategy-id="
            selected.id === requestedProfile
              ? Number(route.query.strategy)
              : undefined
          "
        />
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
      @submit="saveProfile"
    >
      <label class="field">
        <span>{{ $t("profiles.name") }}</span>
        <input v-model="form.name" maxlength="128" required />
      </label>
      <label class="field">
        <span>{{ $t("profiles.venue") }}</span>
        <AppSelect
          v-model="form.venue_type"
          :options="venueOptions"
          :label="$t('profiles.venue')"
          :disabled="editing !== null"
        />
        <small>{{
          editing ? $t("profiles.venueLocked") : $t("profiles.venueHint")
        }}</small>
      </label>
      <label class="field">
        <span>{{ $t("profileMarket.venueUrl") }}</span>
        <input
          v-model="form.venue_url"
          type="url"
          maxlength="2048"
          placeholder="https://…"
        />
        <small>{{ $t("profileMarket.venueUrlHelp") }}</small>
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
      @confirm="removeProfile"
    />
  </section>
</template>

<style scoped>
.profile-console.profile-console--directory {
  min-height: 0;
}
.profile-console--directory .profile-directory {
  border: 0;
  padding: 20px;
}
.profile-console--directory .profile-directory__items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 330px), 1fr));
  gap: 16px;
  overflow: visible;
  border: 0;
}
</style>

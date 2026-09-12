<script setup lang="ts">
/** Switch workspace context while retaining transferable list filters. */
import { computed, ref } from "vue";
import {
  Check,
  ChevronsUpDown,
  Layers,
  Landmark,
  Settings2,
} from "@lucide/vue";
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "reka-ui";
import { useIsMutating, useQuery } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import { listProfiles } from "@/features/profiles/api";
import { useProfileContext } from "@/composables/useProfileContext";

const route = useRoute();
defineProps<{ compact?: boolean }>();
const open = ref(false);
const router = useRouter();
const { profileId } = useProfileContext();
const mutations = useIsMutating();
const profiles = useQuery({ queryKey: ["profiles"], queryFn: listProfiles });
const active = computed(
  () => profiles.data.value?.filter((profile) => !profile.is_archived) ?? [],
);
const archived = computed(
  () => profiles.data.value?.filter((profile) => profile.is_archived) ?? [],
);
const selected = computed(() =>
  profiles.data.value?.find((profile) => profile.id === profileId.value),
);

/** Resource-specific filters and individual trades never cross profiles. */
async function switchContext(value: unknown): Promise<void> {
  if (typeof value !== "string") return;
  const next = Number(value) || null;
  open.value = false;
  if (next === profileId.value) return;
  const section =
    route.path.match(
      /\/(trades|analytics|market|wallet|strategies)(?:\/|$)/,
    )?.[1] ?? "trades";
  const targetSection =
    next === null && !["trades", "analytics"].includes(section)
      ? "trades"
      : section;
  const query = Object.fromEntries(
    Object.entries(route.query).filter(([key]) =>
      [
        "period",
        "date_from",
        "date_to",
        "direction",
        "trade_status",
        "review",
        "rating",
        "sort",
        "order",
      ].includes(key),
    ),
  );
  await router.push({
    path: `${next === null ? "" : `/profiles/${next}`}/${targetSection}`,
    query,
  });
}
</script>

<template>
  <div class="profile-context" :class="{ 'profile-context--compact': compact }">
    <DropdownMenuRoot v-model:open="open">
      <DropdownMenuTrigger
        class="profile-context__trigger"
        :disabled="mutations > 0 || profiles.isPending.value"
        :aria-label="`${$t('context.label')}: ${selected?.name ?? $t('journal.allProfiles')}`"
        :title="
          compact ? (selected?.name ?? $t('journal.allProfiles')) : undefined
        "
      >
        <span class="profile-context__mark"
          ><component :is="profileId ? Landmark : Layers" :size="18"
        /></span>
        <span v-if="!compact" class="profile-context__copy">
          <small>{{ $t("context.label") }}</small>
          <strong>{{ selected?.name ?? $t("journal.allProfiles") }}</strong>
        </span>
        <ChevronsUpDown
          v-if="!compact"
          :size="15"
          class="profile-context__chevron"
        />
      </DropdownMenuTrigger>
      <DropdownMenuPortal>
        <DropdownMenuContent
          class="profile-context-menu"
          :side="compact ? 'right' : 'bottom'"
          align="start"
          :side-offset="8"
          :collision-padding="12"
        >
          <DropdownMenuLabel class="profile-context-menu__label">{{
            $t("context.label")
          }}</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            :model-value="String(profileId ?? '')"
            @update:model-value="switchContext"
          >
            <DropdownMenuRadioItem class="profile-context-menu__item" value="">
              <Layers :size="17" /><span>{{ $t("journal.allProfiles") }}</span
              ><Check v-if="profileId === null" :size="16" />
            </DropdownMenuRadioItem>
            <DropdownMenuSeparator class="profile-context-menu__separator" />
            <DropdownMenuRadioItem
              v-for="profile in active"
              :key="profile.id"
              :value="String(profile.id)"
              class="profile-context-menu__item"
            >
              <Landmark :size="17" /><span>{{ profile.name }}</span
              ><Check v-if="profileId === profile.id" :size="16" />
            </DropdownMenuRadioItem>
            <DropdownMenuLabel
              v-if="archived.length"
              class="profile-context-menu__label"
              >{{ $t("profiles.visibility.archived") }}</DropdownMenuLabel
            >
            <DropdownMenuRadioItem
              v-for="profile in archived"
              :key="profile.id"
              :value="String(profile.id)"
              class="profile-context-menu__item profile-context-menu__item--archived"
            >
              <Landmark :size="17" /><span>{{ profile.name }}</span
              ><Check v-if="profileId === profile.id" :size="16" />
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
          <DropdownMenuItem
            v-if="profiles.isError.value"
            class="profile-context-menu__item"
            @select="profiles.refetch()"
            >{{ $t("common.retry") }}</DropdownMenuItem
          >
          <DropdownMenuSeparator class="profile-context-menu__separator" />
          <DropdownMenuItem
            class="profile-context-menu__item"
            @select="router.push('/profiles')"
            ><Settings2 :size="17" /><span>{{
              $t("nav.profiles")
            }}</span></DropdownMenuItem
          >
        </DropdownMenuContent>
      </DropdownMenuPortal>
    </DropdownMenuRoot>
  </div>
</template>

<style scoped>
.profile-context {
  display: block;
  padding: 12px 0;
  min-width: 0;
}
.profile-context__trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--tf-line);
  border-radius: var(--tf-radius-sm);
  background: var(--tf-panel);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.profile-context__trigger:hover,
.profile-context__trigger[data-state="open"] {
  border-color: var(--tf-action);
}
.profile-context__trigger:disabled {
  opacity: 0.5;
  cursor: wait;
}
.profile-context__trigger:focus-visible {
  outline: 2px solid var(--tf-action);
  outline-offset: 2px;
}
.profile-context__mark {
  display: grid;
  place-items: center;
  color: var(--tf-action);
  flex-shrink: 0;
}
.profile-context__copy {
  display: grid;
  gap: 3px;
  flex: 1;
  min-width: 0;
}
.profile-context__copy small {
  color: var(--tf-ink-soft);
  font-size: 10px;
}
.profile-context__copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
}
.profile-context__chevron {
  color: var(--tf-ink-faint);
  flex-shrink: 0;
}
.profile-context--compact .profile-context__trigger {
  justify-content: center;
  width: 40px;
  height: 40px;
  margin: auto;
  padding: 0;
}
</style>

<style>
/* Portalled menu content lives outside the component's scoped DOM root. */
.profile-context-menu {
  z-index: 100;
  width: 260px;
  max-width: calc(100vw - 24px);
  max-height: min(420px, var(--reka-dropdown-menu-content-available-height));
  overflow-y: auto;
  padding: 6px;
  border: 1px solid var(--tf-line);
  border-radius: var(--tf-radius-md);
  background: var(--tf-panel);
  color: var(--tf-ink);
  box-shadow: var(--tf-shadow);
}
.profile-context-menu__label {
  padding: 8px 10px;
  color: var(--tf-ink-soft);
  font-size: 11px;
}
.profile-context-menu__item {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 40px;
  padding: 8px 10px;
  border-radius: 7px;
  font-size: 13px;
  cursor: pointer;
  outline: none;
}
.profile-context-menu__item span {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.profile-context-menu__item svg {
  flex-shrink: 0;
  color: var(--tf-ink-soft);
}
.profile-context-menu__item[data-highlighted] {
  background: var(--tf-panel-raised);
}
.profile-context-menu__item[data-state="checked"] {
  color: var(--tf-action);
  background: var(--tf-action-soft);
}
.profile-context-menu__item--archived {
  color: var(--tf-ink-soft);
}
.profile-context-menu__separator {
  height: 1px;
  margin: 6px;
  background: var(--tf-line);
}
</style>

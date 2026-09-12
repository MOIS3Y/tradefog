<script setup lang="ts">
/** A profile entry with journal context and direct working-section links. */
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { ArrowUpRight, Landmark, WalletCards, Target } from "@lucide/vue";
import { useI18n } from "vue-i18n";
import type { Profile } from "./api";
import { listTrades } from "@/features/trades/api";

const props = defineProps<{ profile: Profile }>();
const { locale } = useI18n();
const root = computed(() => `/profiles/${props.profile.id}`);
const journal = useQuery({
  queryKey: computed(() => [
    "trades",
    "list",
    "profile-card",
    props.profile.id,
  ]),
  queryFn: () =>
    listTrades(
      { page: 1, page_size: 1, sort: "trade_date", order: "desc" },
      props.profile.id,
    ),
});
const latest = computed(() => {
  const date = journal.data.value?.items[0]?.trade_date;
  return date
    ? new Intl.DateTimeFormat(locale.value, {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(`${date}T00:00:00Z`))
    : null;
});
</script>

<template>
  <article
    class="profile-card"
    :class="{ 'profile-card--archived': profile.is_archived }"
  >
    <header class="profile-card__heading">
      <span class="profile-card__mark"><Landmark :size="20" /></span>
      <div class="profile-card__identity">
        <RouterLink class="profile-card__title" :to="`${root}/trades`"
          >{{ profile.name }}<ArrowUpRight :size="17"
        /></RouterLink>
        <span class="profile-card__venue">{{
          profile.venue_type === "bybit" ? "Bybit" : $t("profileMarket.manual")
        }}</span>
      </div>
      <span
        class="profile-card__status"
        :class="{ 'profile-card__status--archived': profile.is_archived }"
        >{{
          $t(
            profile.is_archived
              ? "profileCards.archived"
              : "profileCards.active",
          )
        }}</span
      >
    </header>
    <p class="profile-card__description">
      {{ profile.description || $t("profileCards.noDescription") }}
    </p>
    <dl class="profile-card__facts" :aria-busy="journal.isPending.value">
      <div>
        <dt>{{ $t("profileCards.trades") }}</dt>
        <dd>{{ journal.data.value?.total ?? "—" }}</dd>
      </div>
      <div>
        <dt>{{ $t("profileCards.latest") }}</dt>
        <dd>
          {{
            latest ??
            (journal.isSuccess.value ? $t("profileCards.noTrades") : "—")
          }}
        </dd>
      </div>
    </dl>
    <button
      v-if="journal.isError.value"
      class="button-link"
      type="button"
      @click="journal.refetch()"
    >
      {{ $t("profileCards.retry") }}
    </button>
    <footer class="profile-card__links">
      <RouterLink :to="`${root}/wallet`"
        ><WalletCards :size="15" />{{ $t("profiles.wallet.tab") }}</RouterLink
      >
      <RouterLink :to="`${root}/strategies`"
        ><Target :size="15" />{{ $t("profiles.strategies.tab") }}</RouterLink
      >
      <RouterLink class="profile-card__setup" :to="`${root}/market`"
        >{{ $t("profileCards.setup") }}<ArrowUpRight :size="14"
      /></RouterLink>
    </footer>
  </article>
</template>

<style scoped>
article.profile-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 20px;
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--tf-line);
  border-radius: var(--tf-radius-md);
  background: var(--tf-panel);
  color: var(--tf-ink);
  cursor: default;
}
.profile-card:hover {
  border-color: var(--tf-ink-faint);
  background: var(--tf-panel);
}
.profile-card__heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.profile-card__identity {
  flex: 1;
  min-width: 0;
}
.profile-card__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 17px;
  font-weight: 600;
  overflow-wrap: anywhere;
  color: var(--tf-ink-strong);
  text-decoration: none;
}
.profile-card__title svg {
  flex-shrink: 0;
  color: var(--tf-ink-faint);
}
.profile-card__venue {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--tf-ink-soft);
}
.profile-card__status {
  align-self: flex-start;
  padding: 4px 7px;
  border-radius: 5px;
  background: var(--tf-action-soft);
  color: var(--tf-action);
  font-size: 10px;
}
.profile-card__status--archived {
  color: var(--tf-ink-soft);
  background: var(--tf-panel-raised);
}
.profile-card__description {
  margin: 0;
  color: var(--tf-ink-soft);
  font-size: 13px;
  line-height: 1.55;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.profile-card__facts {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 16px;
  margin: auto 0 0;
  padding-top: 4px;
}
.profile-card__facts dt {
  margin-bottom: 7px;
  color: var(--tf-ink-soft);
  font-size: 11px;
}
.profile-card__facts dd {
  margin: 0;
  font-family: var(--tf-mono);
  font-size: 14px;
}
.profile-card__links {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  border-top: 1px solid var(--tf-line-soft);
  padding-top: 15px;
}
.profile-card__links a {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--tf-ink-soft);
  text-decoration: none;
}
.profile-card__links a:hover,
.profile-card__title:hover {
  color: var(--tf-action);
}
.profile-card__links .profile-card__setup {
  margin-left: auto;
}
.profile-card a:focus-visible {
  outline: 2px solid var(--tf-action);
  outline-offset: 4px;
  border-radius: 3px;
}
</style>

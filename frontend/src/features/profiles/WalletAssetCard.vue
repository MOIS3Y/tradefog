<script setup lang="ts">
/** One account denomination: selection and actions are sibling controls. */
import { Archive, ArchiveRestore, Pencil, Plus, Trash2 } from "@lucide/vue";
import type { Asset } from "./marketApi";
import { formatDecimal } from "@/utils/decimal";

defineProps<{ asset: Asset; selected: boolean; archivedProfile: boolean }>();
const emit = defineEmits<{
  select: [];
  edit: [];
  operation: [];
  archive: [];
  delete: [];
}>();
const metrics = ["available", "allocated", "reserved", "uncommitted"] as const;
</script>

<template>
  <article
    class="wallet-balance-card"
    :class="{
      'wallet-balance-card--selected': selected,
      'wallet-balance-card--archived': asset.is_archived,
    }"
  >
    <button
      class="wallet-balance-card__select"
      type="button"
      :aria-pressed="selected"
      @click="emit('select')"
    >
      <span class="wallet-balance-card__heading"
        ><strong>{{ asset.symbol }}</strong>
        <span class="health-dot" :class="`health-dot--${asset.status}`"
      /></span>
      <small class="wallet-balance-card__name"
        ><template v-if="asset.name?.trim()"
          >{{ asset.name.trim() }} · </template
        >{{ $t(`catalog.types.${asset.asset_type}`) }}</small
      >
      <span class="wallet-balance-card__balance">{{
        formatDecimal(asset.balance)
      }}</span>
      <span class="wallet-balance-card__metrics">
        <small v-for="key in metrics" :key="key"
          ><span>{{ $t(`profiles.wallet.${key}`) }}</span>
          <b>{{ formatDecimal(asset[key]) }}</b></small
        >
        <small
          ><span>{{ $t("profiles.wallet.riskFloor") }}</span>
          <b>{{
            asset.risk_stop_capital === null
              ? "—"
              : formatDecimal(asset.risk_stop_capital)
          }}</b></small
        >
      </span>
    </button>
    <div class="wallet-balance-card__actions">
      <button
        class="icon-action"
        type="button"
        :disabled="archivedProfile || asset.is_archived"
        :aria-label="$t('profiles.wallet.addOperation') + ' · ' + asset.symbol"
        :title="$t('profiles.wallet.addOperation')"
        @click="emit('operation')"
      >
        <Plus :size="16" />
      </button>
      <button
        class="icon-action"
        type="button"
        :disabled="archivedProfile"
        :aria-label="$t('catalog.edit') + ' · ' + asset.symbol"
        :title="$t('catalog.edit')"
        @click="emit('edit')"
      >
        <Pencil :size="15" />
      </button>
      <button
        class="icon-action"
        type="button"
        :disabled="archivedProfile"
        :aria-label="
          $t(
            asset.is_archived
              ? 'profiles.wallet.restoreAsset'
              : 'profiles.wallet.archiveAsset',
          ) +
          ' · ' +
          asset.symbol
        "
        :title="
          $t(
            asset.is_archived
              ? 'profiles.wallet.restoreAsset'
              : 'profiles.wallet.archiveAsset',
          )
        "
        @click="emit('archive')"
      >
        <ArchiveRestore v-if="asset.is_archived" :size="15" /><Archive
          v-else
          :size="15"
        />
      </button>
      <button
        v-if="asset.is_archived"
        class="icon-action icon-action--danger"
        type="button"
        :disabled="archivedProfile"
        :aria-label="$t('catalog.delete') + ' · ' + asset.symbol"
        :title="$t('catalog.delete')"
        @click="emit('delete')"
      >
        <Trash2 :size="15" />
      </button>
    </div>
  </article>
</template>

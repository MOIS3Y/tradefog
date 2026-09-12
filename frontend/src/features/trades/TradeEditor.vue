<script setup lang="ts">
import { useLeaveGuard } from "@/composables/useLeaveGuard";
import {
  Activity,
  ArchiveX,
  BriefcaseBusiness,
  Check,
  CircleDollarSign,
  Gauge,
  LockKeyhole,
  NotebookPen,
  RefreshCw,
  Save,
  Trash2,
  WalletCards,
} from "@lucide/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";

import { ApiError } from "@/api/errors";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import FormDialog from "@/components/FormDialog.vue";
import type { Profile, Strategy } from "@/features/profiles/api";
import { assessChecklist } from "@/features/trades/checklist";
import PositionRiskBar from "@/features/trades/PositionRiskBar.vue";
import TradeAttachments from "@/features/trades/TradeAttachments.vue";
import TradeMarketWorkspace from "@/features/trades/TradeMarketWorkspace.vue";
import TradeRating from "@/features/trades/TradeRating.vue";
import TradeTimestamps from "@/features/trades/TradeTimestamps.vue";
import {
  calculateAtrUsage,
  calculateCapitalRemaining,
  calculateLocalPosition,
  calculatePlannedProfit,
  calculateTargetRisk,
  LocalPlanningError,
  normalizeToStep,
  previewPosition,
} from "@/features/trades/planning";
import {
  cancelTrade,
  closeTrade,
  deleteTrade,
  getPlanningContext,
  openTrade,
  refreshATR,
  saveChecklist,
  savePlan,
  setReviewed,
  submitTrade,
  updateTrade,
  type ChecklistWrite,
  type DirectionalValue,
  type Trade,
} from "@/features/trades/api";
import type { Instrument, Asset } from "@/features/profiles/marketApi";
import { useToastStore } from "@/stores/toasts";
import {
  compareDecimal,
  formatDecimal,
  formatAtrAmount,
  formatRoundedDecimal,
  isPositiveDecimal,
} from "@/utils/decimal";

const props = defineProps<{
  trade: Trade;
  profile?: Profile;
  strategy?: Strategy & { profileId?: number };
  instrument?: Instrument;
  base?: Asset;
  quote?: Asset;
}>();
const emit = defineEmits<{ updated: [trade: Trade]; deleted: [] }>();
const { t } = useI18n();
const queryClient = useQueryClient();
const toasts = useToastStore();
const notes = ref(props.trade.description_markdown ?? "");
const direction = ref(props.trade.direction);
const entry = ref(
  formatDecimal(
    props.trade.preparation.planned_entry ??
      props.trade.snapshot?.planned_entry ??
      "",
  ),
);
const stop = ref(
  formatDecimal(
    props.trade.preparation.planned_stop ??
      props.trade.snapshot?.planned_stop ??
      "",
  ),
);
const manualATR = ref("");
const manualSessionRange = ref("");
const atrMode = ref<"automatic" | "manual">(
  props.profile?.venue_type === "manual" ? "manual" : "automatic",
);
const normalizedField = ref<"entry" | "stop" | null>(null);
const confirmAction = ref<"cancel" | "delete" | null>(null);
const closeOpen = ref(false);
const closeForm = reactive({
  realized_pnl: "",
  actual_exit_price: "",
  total_commission: "",
  funding_result: "",
});
const checklist = reactive<ChecklistWrite>({
  market_sentiment: props.trade.checklist.market_sentiment ?? null,
  information_background: props.trade.checklist.information_background ?? null,
  global_daily_direction: props.trade.checklist.global_daily_direction ?? null,
  local_daily_movement: props.trade.checklist.local_daily_movement ?? null,
});
let normalizationTimer: ReturnType<typeof setTimeout> | null = null;
const isDraft = computed(() => props.trade.status === "draft");
const planningQuery = useQuery({
  queryKey: ["trade-plan-context", props.trade.profile_id, props.trade.id],
  queryFn: () => getPlanningContext(props.trade.profile_id, props.trade.id),
  enabled: isDraft,
  staleTime: 30_000,
  refetchOnWindowFocus: (query) =>
    query.state.status === "error" ? "always" : true,
  retry: (count, error) =>
    !(error instanceof ApiError && error.status === 409) && count < 2,
});
const allocationRequired = computed(
  () =>
    planningQuery.error.value instanceof ApiError &&
    planningQuery.error.value.code === "settlement_allocation_required",
);
/** Open setup separately so unsaved draft inputs remain intact. */
function capitalSetup(tab: "strategies" | "wallet") {
  return {
    path: `/profiles/${props.trade.profile_id}/${tab}`,
    query: {
      strategy: props.trade.strategy_id,
      asset: props.instrument?.settlement_asset_id,
    },
  };
}
const planningResult = computed(() => {
  if (
    !isDraft.value ||
    planningQuery.isError.value ||
    planningQuery.data.value === undefined
  ) {
    return { plan: null, error: null };
  }
  if (!isPositiveDecimal(entry.value) || !isPositiveDecimal(stop.value)) {
    return { plan: null, error: null };
  }
  try {
    return {
      plan: calculateLocalPosition(
        planningQuery.data.value,
        direction.value,
        entry.value,
        stop.value,
        props.trade.atr?.value,
      ),
      error: null,
    };
  } catch (error) {
    return {
      plan: null,
      error:
        error instanceof LocalPlanningError
          ? t(`trades.errors.${error.code}`)
          : t("trades.errors.invalidPlan"),
    };
  }
});
const localPlan = computed(() => planningResult.value.plan);
const planError = computed(() =>
  planningQuery.isError.value
    ? allocationRequired.value
      ? t("trades.errors.allocationRequired", { asset: settlementSymbol.value })
      : t("trades.errors.contextUnavailable")
    : planningResult.value.error,
);
const activePlan = computed(() =>
  isDraft.value ? localPlan.value : props.trade.snapshot,
);
const preview = computed(() =>
  isDraft.value && !planningQuery.isError.value && planningQuery.data.value
    ? previewPosition(
        planningQuery.data.value,
        direction.value,
        entry.value,
        stop.value,
      )
    : null,
);
const knownContext = computed(() =>
  isDraft.value
    ? planningQuery.isError.value
      ? undefined
      : planningQuery.data.value
    : props.trade.snapshot,
);
const ticketWarning = computed(() => {
  if (!planError.value || !preview.value || !planningQuery.data.value)
    return planError.value;
  if (
    compareDecimal(
      planningQuery.data.value.target_risk_amount,
      preview.value.minimumRisk,
    ) >= 0
  )
    return planError.value;
  return t("positionTicket.minimumRisk", {
    quantity: formatDecimal(preview.value.minimumQuantity),
    required: formatDecimal(preview.value.minimumRisk),
    available: formatDecimal(planningQuery.data.value.target_risk_amount),
    asset: settlementSymbol.value,
  });
});
const target = computed(
  () =>
    activePlan.value?.planned_take_profit?.toString() ??
    preview.value?.target ??
    "",
);
const targetRisk = computed(() =>
  isDraft.value
    ? planningQuery.isError.value
      ? "—"
      : (planningQuery.data.value?.target_risk_amount ?? "—")
    : calculateTargetRisk(
        props.trade.snapshot?.allocation_capital,
        props.trade.snapshot?.planned_risk_percent,
      ),
);
const plannedProfit = computed(() =>
  calculatePlannedProfit(
    activePlan.value?.planned_risk_amount,
    activePlan.value?.reward_multiple ?? props.strategy?.reward_multiple,
  ),
);
const targetAtrPercent = computed(
  () =>
    localPlan.value?.take_profit_atr_percent ??
    calculateAtrUsage(
      activePlan.value?.take_profit_distance ?? preview.value?.targetDistance,
      props.trade.atr?.value ?? props.trade.snapshot?.atr_value,
    ),
);
const sessionRange = computed(
  () =>
    props.trade.atr?.observed_session_range ??
    props.trade.preparation.observed_session_range ??
    null,
);
const sessionAtrPercent = computed(
  () =>
    props.trade.atr?.session_range_percent ??
    calculateAtrUsage(
      sessionRange.value,
      props.trade.atr?.value ?? props.trade.snapshot?.atr_value,
    ),
);
const settlementSymbol = computed(() => props.quote?.symbol ?? "");
const buyback = computed(
  () =>
    direction.value === "short" &&
    ["spot", "cash_equity"].includes(
      props.instrument?.product ??
        props.trade.snapshot?.instrument_product ??
        "",
    ),
);
const quoteReservation = computed(
  () =>
    localPlan.value?.settlement_required ??
    props.trade.reservations.find((row) => row.purpose !== "inventory")
      ?.amount ??
    "0",
);
const inventoryReservation = computed(
  () =>
    localPlan.value?.inventory_required ??
    props.trade.reservations.find((row) => row.purpose === "inventory")
      ?.amount ??
    "0",
);
const targetAtrExceeded = computed(
  () =>
    targetAtrPercent.value !== null &&
    compareDecimal(targetAtrPercent.value, "75") > 0,
);
const resultTone = computed(() => {
  const value = props.trade.realized_pnl;
  if (!value || formatDecimal(value) === "0") return "neutral";
  return value.startsWith("-") ? "loss" : "profit";
});
const realizedPnlDisplay = computed(() => {
  const value = props.trade.realized_pnl;
  if (value === null) return "";
  const formatted = formatDecimal(value);
  if (formatted === "0") return formatted;
  return `${formatted.startsWith("-") ? "" : "+"}${formatted}`;
});
const capitalRemaining = computed(() =>
  localPlan.value
    ? localPlan.value.capital_remaining
    : calculateCapitalRemaining(
        props.trade.snapshot?.wallet_available,
        quoteReservation.value,
      ),
);
/** Stable result slots distinguish unavailable values from genuine zeroes. */
const ticketFacts = computed(() => [
  {
    label: t("positionTicket.riskBudget"),
    value: targetRisk.value,
    unit: settlementSymbol.value,
  },

  {
    label: t("trades.plan.available"),
    value: knownContext.value?.wallet_available ?? "—",
    unit: settlementSymbol.value,
  },
  {
    label: t("trades.plan.capitalRemaining"),
    value: activePlan.value ? capitalRemaining.value : "—",
    unit: settlementSymbol.value,
  },
  {
    label: t(
      buyback.value ? "profileMarket.lossBuffer" : "profileMarket.funding",
    ),
    value: activePlan.value ? quoteReservation.value : "—",
    unit: settlementSymbol.value,
  },
  ...(buyback.value
    ? [
        {
          label: t("profileMarket.inventory"),
          value: activePlan.value ? inventoryReservation.value : "—",
          unit: props.base?.symbol ?? "",
        },
      ]
    : []),
]);
const checklistFields = [
  "market_sentiment",
  "information_background",
  "global_daily_direction",
  "local_daily_movement",
] as const;
const answerValues: DirectionalValue[] = ["NEGATIVE", "NEUTRAL", "POSITIVE"];
const checklistAssessment = computed(() => {
  const values = checklistFields.map((field) => checklist[field]);
  return assessChecklist(values, direction.value);
});
const canSubmit = computed(
  () => localPlan.value !== null && localPlan.value.capital_sufficient,
);
const planInput = computed(() => ({
  planned_entry: localPlan.value?.planned_entry ?? entry.value,
  planned_stop: localPlan.value?.planned_stop ?? stop.value,
}));
function cssPercent(value: string | null | undefined): string {
  const match = /^\+?(\d+)/.exec(value ?? "");
  if (match === null) return "0%";
  const whole = BigInt(match[1] ?? "0");
  return `${whole > 100n ? 100n : whole}%`;
}

function reportError(error: unknown, title: string): void {
  const message =
    error instanceof ApiError ? error.message : t("trades.errors.generic");
  toasts.error({ title, description: message });
}

function synchronizeEditor(trade: Trade): void {
  notes.value = trade.description_markdown ?? "";
  direction.value = trade.direction;
  entry.value = formatDecimal(
    trade.preparation.planned_entry ?? trade.snapshot?.planned_entry ?? "",
  );
  stop.value = formatDecimal(
    trade.preparation.planned_stop ?? trade.snapshot?.planned_stop ?? "",
  );
  Object.assign(checklist, {
    market_sentiment: trade.checklist.market_sentiment ?? null,
    information_background: trade.checklist.information_background ?? null,
    global_daily_direction: trade.checklist.global_daily_direction ?? null,
    local_daily_movement: trade.checklist.local_daily_movement ?? null,
  });
}

function acceptTrade(trade: Trade, synchronize = false): void {
  if (synchronize) {
    synchronizeEditor(trade);
    savedEditor.value = editorState();
  }
  emit("updated", trade);
}

function refreshRelatedContext(): void {
  void queryClient.invalidateQueries({ queryKey: ["trade-plan-context"] });
  void queryClient.invalidateQueries({ queryKey: ["profiles"] });
}

function eventValue(event: Event): string {
  return (event.target as HTMLInputElement).value;
}

function handleStopInput(event: Event): void {
  stop.value = eventValue(event);
}

function handleEntryInput(event: Event): void {
  entry.value = eventValue(event);
}

function markNormalized(field: "entry" | "stop"): void {
  normalizedField.value = field;
  if (normalizationTimer !== null) clearTimeout(normalizationTimer);
  normalizationTimer = setTimeout(() => {
    normalizedField.value = null;
  }, 600);
}

function normalizeEntry(): void {
  const step = planningQuery.data.value?.price_step;
  if (!step) return;
  const normalized = normalizeToStep(entry.value, step);
  if (normalized !== entry.value) markNormalized("entry");
  entry.value = normalized;
}

function normalizeStop(): void {
  const step = planningQuery.data.value?.price_step;
  if (!step) return;
  const normalized = normalizeToStep(stop.value, step);
  if (normalized !== stop.value) markNormalized("stop");
  stop.value = normalized;
}

function handleManualATRInput(event: Event): void {
  manualATR.value = eventValue(event);
}

function handleManualSessionRangeInput(event: Event): void {
  manualSessionRange.value = eventValue(event);
}

function handleCloseExitInput(event: Event): void {
  closeForm.actual_exit_price = eventValue(event);
}

function normalizeCloseExit(): void {
  const step = props.trade.snapshot?.price_step ?? props.instrument?.price_step;
  if (!step) return;
  closeForm.actual_exit_price = normalizeToStep(
    closeForm.actual_exit_price,
    step,
  );
}

async function persistChanges(): Promise<Trade> {
  let trade = await updateTrade(props.trade.profile_id, props.trade.id, {
    description_markdown: notes.value || null,
    ...(isDraft.value ? { direction: direction.value } : {}),
  });
  if (!isDraft.value) return trade;
  const savedChecklist = await saveChecklist(
    props.trade.profile_id,
    props.trade.id,
    checklist,
  );
  trade = { ...trade, checklist: savedChecklist };
  trade = await savePlan(props.trade.profile_id, props.trade.id, {
    planned_entry: planInput.value.planned_entry || null,
    planned_stop: planInput.value.planned_stop || null,
  });
  return trade;
}

const editorState = () =>
  JSON.stringify({
    notes: notes.value,
    direction: direction.value,
    entry: entry.value,
    stop: stop.value,
    checklist: { ...checklist },
  });
const savedEditor = ref(editorState());
useLeaveGuard(
  computed(
    () =>
      editorState() !== savedEditor.value ||
      (closeOpen.value && Object.values(closeForm).some(Boolean)),
  ),
);

const saveMutation = useMutation({
  mutationFn: persistChanges,
  onSuccess: (trade) => {
    acceptTrade(trade, true);
    toasts.success({ title: t("trades.changesSaved") });
  },
  onError: (error) => reportError(error, t("trades.saveFailed")),
});
const atrMutation = useMutation({
  mutationFn: (manual: boolean) =>
    refreshATR(
      props.trade.profile_id,
      props.trade.id,
      manual ? manualATR.value : undefined,
      manual ? manualSessionRange.value : undefined,
    ),
  onSuccess: (atr) => {
    manualATR.value = "";
    manualSessionRange.value = "";
    acceptTrade({ ...props.trade, atr });
    toasts.success({ title: t("trades.atr.updated") });
  },
  onError: (error) => reportError(error, t("trades.atr.failed")),
});
const lifecycleMutation = useMutation({
  mutationFn: async (action: "pending" | "open-now" | "open" | "cancel") => {
    if (action === "pending" || action === "open-now") {
      await persistChanges();
      return submitTrade(
        props.trade.profile_id,
        props.trade.id,
        action === "pending" ? "pending_entry" : "open",
      );
    }
    return action === "open"
      ? openTrade(props.trade.profile_id, props.trade.id)
      : cancelTrade(props.trade.profile_id, props.trade.id);
  },
  onSuccess: (trade) => {
    confirmAction.value = null;
    acceptTrade(trade, true);
    refreshRelatedContext();
    toasts.success({ title: t("trades.lifecycleUpdated") });
  },
  onError: (error) => reportError(error, t("trades.lifecycleFailed")),
});
const closeMutation = useMutation({
  mutationFn: () =>
    closeTrade(props.trade.profile_id, props.trade.id, {
      realized_pnl: closeForm.realized_pnl,
      actual_exit_price: closeForm.actual_exit_price,
      total_commission: closeForm.total_commission || null,
      funding_result: closeForm.funding_result || null,
    }),
  onSuccess: (trade) => {
    closeOpen.value = false;
    acceptTrade(trade, true);
    refreshRelatedContext();
    toasts.success({ title: t("trades.closed") });
  },
  onError: (error) => reportError(error, t("trades.lifecycleFailed")),
});
const reviewMutation = useMutation({
  mutationFn: () =>
    setReviewed(
      props.trade.profile_id,
      props.trade.id,
      props.trade.review_completed_at === null,
    ),
  onSuccess: (trade) => acceptTrade(trade),
  onError: (error) => reportError(error, t("trades.saveFailed")),
});
const ratingMutation = useMutation({
  mutationFn: (qualityRating: number | null) =>
    updateTrade(props.trade.profile_id, props.trade.id, {
      quality_rating: qualityRating,
    }),
  onSuccess: (trade) => {
    acceptTrade(trade);
    toasts.success({ title: t("trades.rating.saved") });
  },
  onError: (error) => reportError(error, t("trades.rating.failed")),
});
const deleteMutation = useMutation({
  mutationFn: () => deleteTrade(props.trade.profile_id, props.trade.id),
  onSuccess: () => {
    confirmAction.value = null;
    savedEditor.value = editorState();
    toasts.success({ title: t("trades.deleted") });
  },
  onError: (error) => reportError(error, t("trades.deleteFailed")),
});

/** Navigate only after deletion has settled and released the write guard. */
async function removeDraft(): Promise<void> {
  try {
    await deleteMutation.mutateAsync();
    emit("deleted");
  } catch {
    // The mutation displays the server error and keeps the draft visible.
  }
}

onBeforeUnmount(() => {
  if (normalizationTimer !== null) clearTimeout(normalizationTimer);
});
</script>

<template>
  <article class="trade-detail">
    <header class="trade-detail__header">
      <div>
        <div class="trade-detail__context">
          <span>{{ profile?.name }}</span
          ><span>·</span><span>{{ strategy?.name }}</span>
        </div>
        <div class="trade-detail__title">
          <h2>{{ instrument?.exec_symbol ?? `#${trade.id}` }}</h2>
          <span :class="`direction-badge direction-badge--${direction}`">{{
            $t(`trades.direction.${direction}`)
          }}</span>
          <span :class="`trade-status trade-status--${trade.status}`">{{
            $t(`trades.status.${trade.status}`)
          }}</span>
        </div>
        <p>
          {{ instrument?.exec_symbol }} ·
          {{ instrument ? $t(`venues.products.${instrument.product}`) : "" }} ·
          {{ trade.trade_date }}
        </p>
      </div>
      <TradeRating
        :model-value="trade.quality_rating"
        :label="$t('trades.rating.label')"
        :empty-label="$t('trades.rating.empty')"
        :value-label="
          (value) => $t('trades.rating.value', { value, maximum: 10 })
        "
        :disabled="ratingMutation.isPending.value"
        @update:model-value="ratingMutation.mutate"
      />
    </header>

    <TradeTimestamps :trade="trade" />

    <div class="trade-lifecycle">
      <div class="trade-lifecycle__rail">
        <span
          v-for="status in ['draft', 'pending_entry', 'open', 'closed']"
          :key="status"
          :aria-current="trade.status === status ? 'step' : undefined"
          :class="{
            active: trade.status === status,
            passed:
              ['pending_entry', 'open', 'closed'].indexOf(trade.status) >=
                ['pending_entry', 'open', 'closed'].indexOf(status) &&
              status !== 'draft',
          }"
          >{{ $t(`trades.status.${status}`) }}</span
        >
      </div>
      <div class="trade-lifecycle__actions">
        <button
          class="button button--secondary"
          type="button"
          :disabled="saveMutation.isPending.value"
          @click="saveMutation.mutate()"
        >
          <Save :size="16" />{{ $t("trades.actions.save") }}
        </button>
        <button
          v-if="isDraft"
          class="button button--secondary"
          type="button"
          :disabled="!canSubmit"
          @click="lifecycleMutation.mutate('pending')"
        >
          {{ $t("trades.actions.submit") }}
        </button>
        <button
          v-if="isDraft"
          class="button button--primary"
          type="button"
          :disabled="!canSubmit"
          @click="lifecycleMutation.mutate('open-now')"
        >
          {{ $t("trades.actions.openNow") }}
        </button>
        <button
          v-if="trade.status === 'pending_entry'"
          class="button button--primary"
          type="button"
          @click="lifecycleMutation.mutate('open')"
        >
          {{ $t("trades.actions.markOpen") }}
        </button>
        <button
          v-if="trade.status === 'open'"
          class="button button--primary"
          type="button"
          @click="closeOpen = true"
        >
          {{ $t("trades.actions.closeTrade") }}
        </button>
        <button
          v-if="['draft', 'pending_entry'].includes(trade.status)"
          class="button button--quiet-danger"
          type="button"
          @click="confirmAction = 'cancel'"
        >
          {{ $t("trades.actions.cancelTrade") }}
        </button>
        <button
          v-if="isDraft"
          class="icon-action icon-action--danger"
          type="button"
          :aria-label="$t('trades.actions.delete')"
          @click="confirmAction = 'delete'"
        >
          <Trash2 :size="17" />
        </button>
      </div>
    </div>

    <div class="trade-workgrid">
      <section class="trade-module trade-module--position">
        <TradeMarketWorkspace
          :profile-id="trade.profile_id"
          :trade-id="trade.id"
          :instrument="instrument"
          :venue-type="profile?.venue_type"
          :base="base"
          :quote="quote"
        >
          <header class="trade-module__header">
            <span class="trade-module__icon"
              ><CircleDollarSign :size="18"
            /></span>
            <div>
              <h3>{{ $t("trades.plan.title") }}</h3>
              <p>{{ $t("trades.plan.subtitle") }}</p>
            </div>
            <LockKeyhole
              v-if="!isDraft"
              :size="15"
              class="trade-module__lock"
            />
          </header>
          <div class="position-entry-panel">
            <div
              v-if="isDraft"
              class="direction-switch"
              role="group"
              :aria-label="$t('trades.fields.direction')"
            >
              <button
                type="button"
                :class="{ active: direction === 'long' }"
                @click="direction = 'long'"
              >
                {{ $t("trades.direction.long") }}
              </button>
              <button
                type="button"
                :class="{ active: direction === 'short' }"
                @click="direction = 'short'"
              >
                {{ $t("trades.direction.short") }}
              </button>
            </div>
            <p v-if="buyback" class="position-buyback">
              {{ $t("profileMarket.buybackHelp") }}
            </p>
            <div class="position-fields">
              <label
                class="field field--risk"
                :class="{ 'field--normalized': normalizedField === 'stop' }"
                ><span>{{ $t("trades.plan.stop") }}</span
                ><input
                  :value="stop"
                  type="number"
                  :step="instrument?.price_step ?? 'any'"
                  :disabled="!isDraft"
                  @input="handleStopInput"
                  @blur="normalizeStop"
                  @keydown.enter="normalizeStop"
              /></label>
              <label
                class="field field--entry"
                :class="{ 'field--normalized': normalizedField === 'entry' }"
                ><span>{{ $t("trades.plan.entry") }}</span
                ><input
                  :value="entry"
                  type="number"
                  :step="instrument?.price_step ?? 'any'"
                  :disabled="!isDraft"
                  @input="handleEntryInput"
                  @blur="normalizeEntry"
                  @keydown.enter="normalizeEntry"
              /></label>
              <label class="field field--reward"
                ><span>{{ $t("trades.plan.target") }}</span
                ><input
                  class="derived-price"
                  type="text"
                  readonly
                  :value="formatDecimal(target)"
                  :placeholder="$t('trades.plan.derivedTarget')"
                  :title="$t('trades.plan.derivedTarget')"
              /></label>
            </div>
          </div>
          <div class="position-results-panel">
            <div class="position-ticket__headline">
              <div>
                <span>{{ $t(`trades.plan.quantity.${direction}`) }}</span>
                <strong>{{
                  formatDecimal(activePlan?.quantity ?? "—")
                }}</strong>
                <small>{{ base?.symbol }}</small>
              </div>
              <div>
                <span>{{ $t("trades.plan.notional") }}</span>
                <strong>{{
                  formatDecimal(activePlan?.planned_notional ?? "—")
                }}</strong>
                <small>{{ settlementSymbol }}</small>
              </div>
            </div>
            <PositionRiskBar
              v-if="activePlan || preview"
              :direction="direction"
              :entry="activePlan?.planned_entry ?? preview?.entry ?? entry"
              :stop="activePlan?.planned_stop ?? preview?.stop ?? stop"
              :target="activePlan?.planned_take_profit ?? target"
              :stop-distance="
                activePlan?.stop_distance ?? preview?.distance ?? '0'
              "
              :target-distance="
                activePlan?.take_profit_distance ??
                preview?.targetDistance ??
                '0'
              "
              :exit-price="trade.actual_exit_price"
              :realized-pnl="trade.realized_pnl"
            />
            <div class="position-ticket__outcome">
              <div class="position-ticket__risk">
                <span>{{ $t("trades.plan.actualRisk") }}</span>
                <strong>{{
                  formatDecimal(activePlan?.planned_risk_amount ?? "—")
                }}</strong>
                <small>{{ settlementSymbol }}</small>
              </div>
              <div class="position-ticket__profit">
                <span>{{ $t("trades.plan.profit") }}</span>
                <strong>{{
                  formatDecimal(activePlan ? plannedProfit : "—")
                }}</strong>
                <small>{{ settlementSymbol }}</small>
              </div>
            </div>
            <dl class="position-ticket__facts">
              <div v-for="fact in ticketFacts" :key="fact.label">
                <dt>{{ fact.label }}</dt>
                <dd>
                  {{ formatDecimal(fact.value) }}
                  <small>{{ fact.unit }}</small>
                </dd>
              </div>
              <div>
                <dt>{{ $t("profileMarket.riskRule") }}</dt>
                <dd>
                  {{
                    formatDecimal(knownContext?.planned_risk_percent ?? "—")
                  }}% · 1 :
                  {{
                    formatDecimal(String(knownContext?.reward_multiple ?? "—"))
                  }}
                </dd>
              </div>
              <div v-if="buyback">
                <dt>{{ $t("positionTicket.inventoryAvailable") }}</dt>
                <dd>
                  {{
                    formatDecimal(
                      isDraft
                        ? (planningQuery.data.value?.inventory_available ?? "—")
                        : "—",
                    )
                  }}
                  {{ base?.symbol }}
                </dd>
              </div>
            </dl>
            <p
              v-if="isDraft"
              class="position-ticket__status"
              :class="{ 'position-ticket__status--warning': ticketWarning }"
              role="status"
            >
              {{
                ticketWarning ||
                (activePlan
                  ? $t("positionTicket.preview")
                  : $t("positionTicket.enterPrices"))
              }}
            </p>
            <div
              v-if="isDraft && planningQuery.isError.value"
              class="position-setup-actions"
            >
              <template v-if="allocationRequired">
                <RouterLink
                  class="icon-action"
                  :title="$t('trades.setup.capital')"
                  :aria-label="$t('trades.setup.capital')"
                  :to="capitalSetup('strategies')"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <BriefcaseBusiness :size="18" aria-hidden="true" />
                </RouterLink>
                <RouterLink
                  class="icon-action"
                  :title="$t('trades.setup.wallet')"
                  :aria-label="$t('trades.setup.wallet')"
                  :to="capitalSetup('wallet')"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <WalletCards :size="18" aria-hidden="true" />
                </RouterLink>
              </template>
              <button
                class="icon-action"
                :title="$t('trades.setup.retry')"
                :aria-label="$t('trades.setup.retry')"
                :disabled="planningQuery.isFetching.value"
                @click="planningQuery.refetch()"
              >
                <RefreshCw :size="18" aria-hidden="true" />
              </button>
            </div>
            <div
              v-if="trade.status === 'closed' && trade.realized_pnl !== null"
              class="trade-result"
            >
              <div>
                <small>{{ $t("trades.result.title") }}</small>
                <strong :class="`trade-result__value--${resultTone}`">
                  {{ realizedPnlDisplay }} {{ settlementSymbol }}
                </strong>
              </div>
              <dl>
                <div v-if="trade.actual_exit_price !== null">
                  <dt>{{ $t("trades.close.exit") }}</dt>
                  <dd>{{ formatDecimal(trade.actual_exit_price) }}</dd>
                </div>
                <div v-if="trade.total_commission !== null">
                  <dt>{{ $t("trades.close.commission") }}</dt>
                  <dd>{{ formatDecimal(trade.total_commission) }}</dd>
                </div>
                <div v-if="trade.funding_result !== null">
                  <dt>{{ $t("trades.close.funding") }}</dt>
                  <dd>{{ formatDecimal(trade.funding_result) }}</dd>
                </div>
              </dl>
            </div>
            <div
              v-if="localPlan && !localPlan.capital_sufficient"
              class="capital-alert"
            >
              <ArchiveX :size="18" />
              <div>
                <strong>{{
                  compareDecimal(
                    localPlan.wallet_available,
                    localPlan.settlement_required,
                  ) < 0
                    ? $t("trades.setup.insufficient", {
                        asset: settlementSymbol,
                      })
                    : $t("trades.plan.insufficient")
                }}</strong
                ><span>{{ $t("trades.plan.insufficientBody") }}</span>
              </div>
            </div>
          </div>
        </TradeMarketWorkspace>
      </section>

      <section class="trade-module trade-module--checklist">
        <header class="trade-module__header">
          <span class="trade-module__icon"><Gauge :size="18" /></span>
          <div>
            <h3>{{ $t("trades.checklist.title") }}</h3>
            <p>{{ $t("trades.checklist.subtitle") }}</p>
          </div>
        </header>
        <div class="checklist-gauge">
          <div class="checklist-gauge__track">
            <span :style="{ left: `${checklistAssessment.gauge}%` }"></span>
          </div>
          <div class="checklist-gauge__labels">
            <span>{{ $t("trades.direction.short") }}</span
            ><strong>{{
              $t(`trades.assessment.${checklistAssessment.direction}`)
            }}</strong
            ><span>{{ $t("trades.direction.long") }}</span>
          </div>
        </div>
        <div
          :class="`checklist-verdict checklist-verdict--${checklistAssessment.verdict}`"
        >
          <Activity :size="17" /><span>{{
            $t(`trades.checklist.verdict.${checklistAssessment.verdict}`)
          }}</span>
        </div>
        <div class="checklist-questions">
          <div
            v-for="field in checklistFields"
            :key="field"
            class="checklist-row"
          >
            <span>{{ $t(`trades.checklist.fields.${field}`) }}</span>
            <div>
              <button
                v-for="answer in answerValues"
                :key="answer"
                type="button"
                :disabled="!isDraft"
                :class="{ selected: checklist[field] === answer }"
                @click="checklist[field] = answer"
              >
                {{ $t(`trades.checklist.answers.${answer}`) }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="trade-module trade-module--atr">
        <header class="trade-module__header">
          <span class="trade-module__icon"><Activity :size="18" /></span>
          <div>
            <h3>{{ $t("trades.atr.title") }}</h3>
            <p>{{ $t("trades.atr.subtitle") }}</p>
          </div>
        </header>
        <div v-if="trade.atr || trade.snapshot?.atr_value" class="atr-value">
          <small>ATR(14)</small
          ><strong>{{
            formatAtrAmount(trade.atr?.value ?? trade.snapshot?.atr_value)
          }}</strong
          ><span>{{ trade.atr?.source ?? trade.snapshot?.atr_source }}</span>
        </div>
        <div class="atr-bars">
          <div>
            <div class="atr-bar__label">
              <span>{{ $t("trades.atr.session") }}</span
              ><strong class="atr-bar__values">
                <span
                  >{{ formatAtrAmount(sessionRange) }}
                  {{ settlementSymbol }}</span
                >
                <span
                  >·
                  {{
                    sessionAtrPercent === null
                      ? "—"
                      : formatRoundedDecimal(sessionAtrPercent, 2) + "%"
                  }}</span
                >
              </strong>
            </div>
            <div class="atr-bar">
              <i class="atr-bar__limit"></i
              ><span :style="{ width: cssPercent(sessionAtrPercent) }"></span>
            </div>
          </div>
          <div>
            <div class="atr-bar__label">
              <span>{{ $t("trades.atr.target") }}</span
              ><strong class="atr-bar__values">
                <span
                  >{{
                    formatAtrAmount(
                      activePlan?.take_profit_distance ??
                        preview?.targetDistance,
                    )
                  }}
                  {{ settlementSymbol }}</span
                >
                <span
                  >·
                  {{
                    targetAtrPercent === null
                      ? "—"
                      : formatRoundedDecimal(targetAtrPercent, 2) + "%"
                  }}</span
                >
              </strong>
            </div>
            <div
              class="atr-bar"
              :class="{
                'atr-bar--exceeded': targetAtrExceeded,
              }"
            >
              <i class="atr-bar__limit"></i
              ><span
                :style="{
                  width: cssPercent(targetAtrPercent),
                }"
              ></span>
            </div>
          </div>
        </div>
        <div v-if="isDraft" class="atr-actions">
          <div
            class="atr-mode-switch"
            role="group"
            :aria-label="$t('trades.atr.source')"
          >
            <button
              v-if="profile?.venue_type !== 'manual'"
              type="button"
              :class="{ active: atrMode === 'automatic' }"
              @click="atrMode = 'automatic'"
            >
              {{ $t("trades.atr.automatic") }}
            </button>
            <button
              type="button"
              :class="{ active: atrMode === 'manual' }"
              @click="atrMode = 'manual'"
            >
              {{ $t("trades.atr.manual") }}
            </button>
          </div>
          <div v-if="atrMode === 'automatic'" class="atr-source-panel">
            <button
              class="button button--secondary"
              type="button"
              :disabled="atrMutation.isPending.value"
              @click="atrMutation.mutate(false)"
            >
              <RefreshCw :size="16" />{{ $t("trades.atr.refresh") }}
            </button>
          </div>
          <div v-else class="atr-source-panel atr-source-panel--manual">
            <div class="atr-manual-fields">
              <label class="field"
                ><span>{{ $t("trades.atr.manualValue") }}</span>
                <input
                  :value="manualATR"
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  @input="handleManualATRInput" /></label
              ><label class="field"
                ><span>{{ $t("trades.atr.sessionRange") }}</span>
                <input
                  :value="manualSessionRange"
                  type="number"
                  :step="instrument?.price_step ?? 'any'"
                  placeholder="0.00"
                  @input="handleManualSessionRangeInput"
              /></label>
            </div>
            <button
              class="button button--secondary"
              type="button"
              :disabled="
                atrMutation.isPending.value ||
                !isPositiveDecimal(manualATR) ||
                !isPositiveDecimal(manualSessionRange)
              "
              @click="atrMutation.mutate(true)"
            >
              <Check :size="16" />{{ $t("trades.atr.applyManual") }}
            </button>
          </div>
        </div>
      </section>

      <section class="trade-module trade-module--journal">
        <header class="trade-module__header">
          <span class="trade-module__icon"><NotebookPen :size="18" /></span>
          <div>
            <h3>{{ $t("trades.notes.title") }}</h3>
            <p>{{ $t("trades.notes.subtitle") }}</p>
          </div>
        </header>
        <div class="trade-journal-grid">
          <textarea
            v-model="notes"
            class="trade-notes"
            :placeholder="$t('trades.notes.placeholder')"
          ></textarea>
          <TradeAttachments
            :profile-id="trade.profile_id"
            :trade-id="trade.id"
          />
        </div>
      </section>
    </div>

    <footer v-if="trade.status === 'closed'" class="trade-review">
      <div>
        <strong>{{ $t("trades.review.title") }}</strong
        ><span>{{ $t("trades.review.body") }}</span>
      </div>
      <button
        class="button"
        :class="
          trade.review_completed_at ? 'button--secondary' : 'button--primary'
        "
        type="button"
        @click="reviewMutation.mutate()"
      >
        {{
          $t(
            trade.review_completed_at
              ? "trades.review.reopen"
              : "trades.review.complete",
          )
        }}
      </button>
    </footer>
  </article>

  <ConfirmDialog
    :open="confirmAction !== null"
    :title="
      $t(
        confirmAction === 'delete'
          ? 'trades.confirm.deleteTitle'
          : 'trades.confirm.cancelTitle',
      )
    "
    :description="
      $t(
        confirmAction === 'delete'
          ? 'trades.confirm.deleteBody'
          : 'trades.confirm.cancelBody',
      )
    "
    :confirm-label="
      $t(
        confirmAction === 'delete'
          ? 'trades.actions.delete'
          : 'trades.actions.cancelTrade',
      )
    "
    :cancel-label="$t('common.cancel')"
    :busy="deleteMutation.isPending.value || lifecycleMutation.isPending.value"
    @update:open="confirmAction = null"
    @confirm="
      confirmAction === 'delete'
        ? removeDraft()
        : lifecycleMutation.mutate('cancel')
    "
  />
  <FormDialog
    v-model:open="closeOpen"
    :title="$t('trades.close.title')"
    :description="$t('trades.close.body')"
    :submit-label="$t('trades.actions.closeTrade')"
    :cancel-label="$t('common.cancel')"
    :busy="closeMutation.isPending.value"
    :invalid="
      closeForm.realized_pnl.trim() === '' ||
      !isPositiveDecimal(closeForm.actual_exit_price)
    "
    @submit="closeMutation.mutate()"
  >
    <label class="field"
      ><span>{{ $t("trades.close.pnl") }}</span
      ><input v-model="closeForm.realized_pnl" inputmode="decimal" required
    /></label>
    <div class="close-price-presets">
      <span>{{ $t("trades.close.quickPrice") }}</span>
      <button
        type="button"
        @click="closeForm.actual_exit_price = formatDecimal(stop)"
      >
        {{ $t("trades.plan.stop") }}
      </button>
      <button
        type="button"
        @click="closeForm.actual_exit_price = formatDecimal(entry)"
      >
        {{ $t("trades.plan.entry") }}
      </button>
      <button
        type="button"
        @click="closeForm.actual_exit_price = formatDecimal(target)"
      >
        {{ $t("trades.plan.target") }}
      </button>
    </div>
    <div class="form-grid form-grid--two">
      <label class="field"
        ><span>{{ $t("trades.close.exit") }}</span
        ><input
          :value="closeForm.actual_exit_price"
          type="number"
          :step="instrument?.price_step ?? 'any'"
          @input="handleCloseExitInput"
          @blur="normalizeCloseExit"
          @keydown.enter="normalizeCloseExit"
          required /></label
      ><label class="field"
        ><span>{{ $t("trades.close.commission") }}</span
        ><input v-model="closeForm.total_commission" inputmode="decimal"
      /></label>
    </div>
    <label class="field"
      ><span>{{ $t("trades.close.funding") }}</span
      ><input v-model="closeForm.funding_result" inputmode="decimal"
    /></label>
    <p
      class="position-ticket__status position-ticket__status--warning"
      role="note"
    >
      <strong>{{ $t("trades.close.immutableTitle") }}</strong
      ><br />
      {{ $t("trades.close.immutableBody") }}
    </p>
  </FormDialog>
</template>

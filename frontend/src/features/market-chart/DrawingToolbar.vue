<script setup lang="ts">
/** Grouped drawing controls remain inside the fullscreen chart subtree. */
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  ChevronDown,
  Minus,
  MoveUpRight,
  MoveVertical,
  Layers,
  ListOrdered,
  Type,
  Pencil,
  Trash2,
  MousePointer2,
} from "@lucide/vue";
import {
  DropdownMenuRoot,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  PopoverRoot,
  PopoverTrigger,
  PopoverContent,
  DialogRoot,
  DialogOverlay,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "reka-ui";
import {
  drawingGroups,
  drawingColors,
  defaultDrawingColor,
  type DrawingGroup,
  type DrawingTool,
  type DrawingSelection,
} from "./drawings";

const props = defineProps<{
  ready: boolean;
  selected: DrawingSelection | null;
  active: DrawingTool | null;
  textRequest: { text: string } | null;
}>();
const emit = defineEmits<{
  draw: [DrawingTool];
  cancel: [];
  color: [string];
  remove: [];
  editText: [];
  finishText: [string | null];
}>();
const { t: translate } = useI18n();
const t = (key: string) => translate(`marketChart.${key}`);
const groups = Object.keys(drawingGroups) as DrawingGroup[];
const last = reactive<Record<DrawingGroup, DrawingTool>>({
  lines: "horizontalStraightLine",
  channels: "priceChannelLine",
  fibonacci: "fibonacciLine",
  labels: "simpleAnnotation",
});
const mobileOpen = ref(false);
const color = ref(defaultDrawingColor);
const text = ref("");
const textOpen = computed(() => props.textRequest !== null);
watch(
  () => props.textRequest,
  (request) => {
    if (request) text.value = request.text;
  },
);
watch(
  () => props.selected,
  (selection) => {
    if (selection) color.value = selection.color;
  },
);

/** Every menu choice is explicit, with the last choice on the group button. */
function choose(group: DrawingGroup, tool: DrawingTool): void {
  last[group] = tool;
  mobileOpen.value = false;
  emit("draw", tool);
}

/** Palette and custom input share the same selected-object semantics. */
function chooseColor(value: string): void {
  color.value = value;
  emit("color", value);
}

/** Directional icons distinguish variants inside the named menu. */
function toolIcon(tool: DrawingTool) {
  if (tool.startsWith("horizontal") || tool === "priceLine") return Minus;
  if (tool.startsWith("vertical")) return MoveVertical;
  if (tool === "fibonacciLine") return ListOrdered;
  if (tool === "priceChannelLine" || tool === "parallelStraightLine")
    return Layers;
  if (tool === "simpleAnnotation" || tool === "simpleTag") return Type;
  return MoveUpRight;
}
</script>

<template>
  <div class="drawing-toolbar">
    <button
      class="market-text-button drawing-toolbar__mobile"
      type="button"
      :aria-expanded="mobileOpen"
      @click="mobileOpen = !mobileOpen"
    >
      <Pencil :size="16" /> {{ t("drawing") }} <ChevronDown :size="12" />
    </button>
    <div
      class="drawing-toolbar__controls"
      :class="{ 'is-open': mobileOpen }"
      role="group"
      :aria-label="t('drawing')"
    >
      <button
        type="button"
        class="icon-action"
        :disabled="!ready"
        :aria-label="t('cursor')"
        :title="t('cursor')"
        :aria-pressed="!active"
        @click="emit('cancel')"
      >
        <MousePointer2 :size="16" />
      </button>
      <div v-for="group in groups" :key="group" class="drawing-toolbar__group">
        <button
          type="button"
          class="icon-action"
          :disabled="!ready"
          :title="t(last[group])"
          :aria-label="t(last[group])"
          :aria-pressed="active === last[group]"
          @click="choose(group, last[group])"
        >
          <component :is="toolIcon(last[group])" :size="16" />
        </button>
        <DropdownMenuRoot>
          <DropdownMenuTrigger
            class="drawing-toolbar__arrow"
            :disabled="!ready"
            :aria-label="t(`groups.${group}`)"
            ><ChevronDown :size="12"
          /></DropdownMenuTrigger>
          <DropdownMenuContent
            class="drawing-menu"
            side="right"
            align="start"
            :side-offset="5"
          >
            <DropdownMenuItem
              v-for="tool in drawingGroups[group]"
              :key="tool"
              class="drawing-menu__item"
              @select="choose(group, tool)"
            >
              <component :is="toolIcon(tool)" :size="16" /> {{ t(tool) }}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenuRoot>
      </div>
      <PopoverRoot>
        <PopoverTrigger
          class="icon-action"
          :disabled="!ready"
          :aria-label="t('drawingColor')"
          :title="t('drawingColor')"
        >
          <span class="drawing-swatch" :style="{ backgroundColor: color }" />
        </PopoverTrigger>
        <PopoverContent
          class="drawing-menu drawing-palette"
          side="right"
          :side-offset="5"
        >
          <p>{{ t("drawingColor") }}</p>
          <div class="drawing-palette__swatches">
            <button
              v-for="value in drawingColors"
              :key="value"
              type="button"
              :aria-label="value"
              :aria-pressed="color === value"
              :style="{ backgroundColor: value }"
              @click="chooseColor(value)"
            />
          </div>
          <label
            >{{ t("customColor") }}
            <input
              type="color"
              :value="color"
              @change="chooseColor(($event.target as HTMLInputElement).value)"
            />
          </label>
        </PopoverContent>
      </PopoverRoot>
      <button
        type="button"
        class="icon-action"
        :disabled="selected?.text === undefined"
        :aria-label="t('editText')"
        :title="t('editText')"
        @click="emit('editText')"
      >
        <Pencil :size="16" />
      </button>
      <button
        type="button"
        class="icon-action"
        :disabled="!selected"
        :aria-label="t('remove')"
        :title="t('remove')"
        @click="emit('remove')"
      >
        <Trash2 :size="16" />
      </button>
    </div>
    <DialogRoot
      :open="textOpen"
      @update:open="
        (open) => {
          if (!open) emit('finishText', null);
        }
      "
    >
      <DialogOverlay class="drawing-dialog-overlay" />
      <DialogContent class="drawing-dialog" @escape-key-down.stop>
        <DialogTitle>{{ t("drawingText") }}</DialogTitle>
        <DialogDescription>{{ t("drawingTextHint") }}</DialogDescription>
        <form @submit.prevent="emit('finishText', text)">
          <label
            >{{ t("drawingText") }}
            <input
              v-model="text"
              maxlength="200"
              :aria-label="t('drawingText')"
            />
          </label>
          <div class="tf-dialog-actions">
            <button
              type="button"
              class="button button--secondary"
              @click="emit('finishText', null)"
            >
              {{ t("cancel") }}
            </button>
            <button
              type="submit"
              class="button button--primary"
              :disabled="!text.trim()"
            >
              {{ t("applyText") }}
            </button>
          </div>
        </form>
      </DialogContent>
    </DialogRoot>
  </div>
</template>

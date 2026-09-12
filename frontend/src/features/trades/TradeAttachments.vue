<script setup lang="ts">
import { FileImage, LoaderCircle, Trash2, Upload } from "@lucide/vue";
import { useMutation, useQuery } from "@tanstack/vue-query";
import "photoswipe/style.css";
import { onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";

import { ApiError } from "@/api/errors";
import {
  deleteAttachment,
  fetchAttachmentContent,
  listAttachments,
  uploadAttachment,
  type Attachment,
} from "@/features/trades/api";
import { useToastStore } from "@/stores/toasts";

interface Slide {
  src: string;
  width: number;
  height: number;
  alt: string;
}

const props = defineProps<{ profileId: number; tradeId: number }>();
const { t } = useI18n();
const toasts = useToastStore();
const slides = ref(new Map<number, Slide>());

const attachmentQuery = useQuery({
  queryKey: ["trade-attachments", props.profileId, props.tradeId],
  queryFn: () => listAttachments(props.profileId, props.tradeId),
});

function reportError(error: unknown): void {
  toasts.error({
    title: t("trades.attachments.failed"),
    description:
      error instanceof ApiError ? error.message : t("trades.errors.generic"),
  });
}

const uploadMutation = useMutation({
  mutationFn: (file: File) =>
    uploadAttachment(props.profileId, props.tradeId, file),
  onSuccess: async () => {
    await attachmentQuery.refetch();
    toasts.success({ title: t("trades.attachments.uploaded") });
  },
  onError: reportError,
});
const removeMutation = useMutation({
  mutationFn: (id: number) =>
    deleteAttachment(props.profileId, props.tradeId, id),
  onSuccess: async (_, id) => {
    const slide = slides.value.get(id);
    if (slide) URL.revokeObjectURL(slide.src);
    slides.value.delete(id);
    await attachmentQuery.refetch();
  },
  onError: reportError,
});

async function loadSlide(item: Attachment): Promise<Slide> {
  const existing = slides.value.get(item.id);
  if (existing) return existing;
  const blob = await fetchAttachmentContent(item);
  const src = URL.createObjectURL(blob);
  const bitmap = await createImageBitmap(blob);
  const slide = {
    src,
    width: bitmap.width,
    height: bitmap.height,
    alt: item.original_name,
  };
  bitmap.close();
  slides.value.set(item.id, slide);
  return slide;
}

async function openGallery(selected: Attachment): Promise<void> {
  try {
    const attachments = attachmentQuery.data.value ?? [];
    const dataSource = await Promise.all(attachments.map(loadSlide));
    const { default: PhotoSwipe } = await import("photoswipe");
    const gallery = new PhotoSwipe({
      dataSource,
      index: attachments.findIndex((item) => item.id === selected.id),
      bgOpacity: 0.94,
      showHideAnimationType: "fade",
    });
    gallery.init();
  } catch (error) {
    reportError(error);
  }
}

function selectFile(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) uploadMutation.mutate(file);
  input.value = "";
}

onBeforeUnmount(() => {
  for (const slide of slides.value.values()) URL.revokeObjectURL(slide.src);
});
</script>

<template>
  <section class="trade-media">
    <header class="trade-media__header">
      <div>
        <h4>{{ $t("trades.attachments.title") }}</h4>
        <p>{{ $t("trades.attachments.subtitle") }}</p>
      </div>
      <label
        class="icon-action attachment-upload"
        :aria-label="$t('trades.attachments.upload')"
      >
        <Upload :size="17" />
        <input
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          @change="selectFile"
        />
      </label>
    </header>
    <div class="attachment-list">
      <div
        v-for="item in attachmentQuery.data.value ?? []"
        :key="item.id"
        class="attachment-card"
      >
        <button
          class="attachment-card__open"
          type="button"
          @click="openGallery(item)"
        >
          <span><FileImage :size="18" /></span>
          <span>
            <strong>{{ item.original_name }}</strong>
            <small>{{ Math.ceil(item.size_bytes / 1024) }} KB</small>
          </span>
        </button>
        <button
          class="icon-action icon-action--danger"
          type="button"
          :aria-label="$t('trades.attachments.delete')"
          @click="removeMutation.mutate(item.id)"
        >
          <Trash2 :size="15" />
        </button>
      </div>
      <p v-if="(attachmentQuery.data.value ?? []).length === 0">
        {{ $t("trades.attachments.empty") }}
      </p>
      <LoaderCircle
        v-if="uploadMutation.isPending.value"
        class="tf-spin"
        :size="20"
      />
    </div>
  </section>
</template>

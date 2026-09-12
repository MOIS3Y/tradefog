<script setup lang="ts">
/** Resolve a direct profile URL before mounting any working controls. */
import { computed, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import {
  useProfileContext,
  rememberProfileContext,
} from "@/composables/useProfileContext";
import { useAuthStore } from "@/stores/auth";
import { getProfile } from "@/features/profiles/api";
import { ApiError } from "@/api/errors";
import LoadingState from "@/components/LoadingState.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";

const { profileId } = useProfileContext();
const auth = useAuthStore();
const profile = useQuery({
  queryKey: computed(() => ["profiles", "detail", profileId.value]),
  enabled: computed(() => profileId.value !== null),
  queryFn: () => getProfile(profileId.value!),
  retry: (count, error) =>
    !(error instanceof ApiError && error.status === 404) && count < 2,
});
const missing = computed(
  () =>
    profile.error.value instanceof ApiError &&
    profile.error.value.status === 404,
);
watch(
  () => profile.data.value,
  (value) => {
    if (auth.user && value?.id === profileId.value) {
      rememberProfileContext(auth.user.id, value.id);
    }
  },
  { immediate: true },
);
</script>

<template>
  <slot v-if="profileId === null" />
  <EmptyState
    v-else-if="missing"
    :title="$t('notFound.title')"
    :description="$t('notFound.body')"
  >
    <RouterLink class="button button--secondary" to="/profiles">{{
      $t("context.chooseProfile")
    }}</RouterLink>
  </EmptyState>
  <ErrorState v-else-if="profile.isError.value" @retry="profile.refetch()" />
  <LoadingState v-else-if="profile.isPending.value" />
  <slot v-else />
</template>

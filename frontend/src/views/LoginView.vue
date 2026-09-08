<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/errors";
import BrandMark from "@/components/BrandMark.vue";
import LanguageMenu from "@/components/LanguageMenu.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const username = ref("");
const password = ref("");
const errorMessage = ref("");
const submitting = ref(false);

async function submit(): Promise<void> {
  errorMessage.value = "";
  submitting.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    const redirect =
      typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(redirect);
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof ApiError && error.status === 401
        ? t("auth.invalid")
        : t("auth.unavailable");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <div class="login-panel__language"><LanguageMenu /></div>
    <section class="login-manifesto" aria-label="Tradefog">
      <a class="wordmark wordmark--light" href="/">
        <BrandMark />
        <span>Tradefog</span>
      </a>
      <div class="manifesto-copy">
        <span class="manifesto-index">1R</span>
        <blockquote>{{ $t("dashboard.maxim") }}</blockquote>
        <p>{{ $t("dashboard.discipline") }}</p>
      </div>
      <div class="risk-preview" aria-hidden="true">
        <div class="risk-preview__header">
          <span>R / DISCIPLINE</span>
          <span class="risk-preview__status">CONTROLLED</span>
        </div>
        <svg viewBox="0 0 600 150" preserveAspectRatio="none">
          <defs>
            <linearGradient id="risk-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#36d98d" stop-opacity="0.28" />
              <stop offset="1" stop-color="#36d98d" stop-opacity="0" />
            </linearGradient>
          </defs>
          <path
            class="risk-preview__area"
            d="M0 123L52 112L98 116L142 88L190 98L238 62L282 75L330 49L376 66L425 39L478 52L530 24L600 33V150H0Z"
          />
          <path
            class="risk-preview__line"
            d="M0 123L52 112L98 116L142 88L190 98L238 62L282 75L330 49L376 66L425 39L478 52L530 24L600 33"
          />
        </svg>
        <div class="manifesto-ruler">
          <span>0R</span>
          <span>½R</span>
          <span>1R</span>
        </div>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-form-wrap">
        <span class="login-form-wrap__glow" aria-hidden="true"></span>
        <p class="eyebrow">{{ $t("auth.eyebrow") }}</p>
        <h1>{{ $t("auth.title") }}</h1>
        <p class="login-lead">{{ $t("auth.subtitle") }}</p>

        <form class="login-form" @submit.prevent="submit">
          <label>
            <span>{{ $t("auth.username") }}</span>
            <input
              v-model="username"
              name="username"
              autocomplete="username"
              required
              autofocus
            />
          </label>
          <label>
            <span>{{ $t("auth.password") }}</span>
            <input
              v-model="password"
              name="password"
              type="password"
              autocomplete="current-password"
              required
            />
          </label>
          <p v-if="errorMessage" class="form-error" role="alert">
            {{ errorMessage }}
          </p>
          <button
            class="button button--primary"
            type="submit"
            :disabled="submitting"
          >
            {{ submitting ? $t("auth.signingIn") : $t("auth.signIn") }}
          </button>
        </form>
        <p class="setup-note">{{ $t("auth.setup") }}</p>
      </div>
    </section>
  </main>
</template>

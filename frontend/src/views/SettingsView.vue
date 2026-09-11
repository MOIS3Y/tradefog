<script setup lang="ts">
/** Self-service settings; each form owns its save and error state. */
import {
  Check,
  Languages,
  LockKeyhole,
  Settings,
  ShieldCheck,
  UserRound,
} from "@lucide/vue";
import { useMutation } from "@tanstack/vue-query";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "reka-ui";
import { computed, onUnmounted, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/errors";
import PanelHeading from "@/components/PanelHeading.vue";
import { changePassword, updateAccount } from "@/features/settings/api";
import AppShell from "@/layouts/AppShell.vue";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toasts";

const auth = useAuthStore();
const toasts = useToastStore();
const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const narrowScreen = window.matchMedia?.("(max-width: 900px)");
const horizontalTabs = ref(narrowScreen?.matches ?? false);

/** Match keyboard navigation to the responsive visual tab orientation. */
function updateOrientation(event: MediaQueryListEvent): void {
  horizontalTabs.value = event.matches;
}
narrowScreen?.addEventListener("change", updateOrientation);
onUnmounted(() =>
  narrowScreen?.removeEventListener("change", updateOrientation),
);
const tabs = [
  { value: "account", icon: UserRound },
  { value: "interface", icon: Languages },
  { value: "security", icon: ShieldCheck },
] as const;
const activeTab = computed(() =>
  route.query.tab === "interface" || route.query.tab === "security"
    ? route.query.tab
    : "account",
);
const form = reactive({
  first_name: auth.user?.first_name ?? "",
  last_name: auth.user?.last_name ?? "",
  email: auth.user?.email ?? "",
});
const selectedLocale = ref<"en" | "ru">(locale.value === "ru" ? "ru" : "en");
const passwords = reactive({
  current_password: "",
  new_password: "",
  confirm: "",
});
const passwordError = ref("");

/** Route state makes settings tabs bookmarkable and browser-back aware. */
function selectTab(value: string | number): void {
  void router.replace({ query: { ...route.query, tab: String(value) } });
}

/** Keep secrets local to the security panel and its current submission. */
function clearPasswords(): void {
  passwords.current_password = "";
  passwords.new_password = "";
  passwords.confirm = "";
}

watch(activeTab, () => {
  clearPasswords();
  passwordError.value = "";
});

/** Never expose raw transport errors or untranslated validation messages. */
function errorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "current_password_invalid") return "currentInvalid";
    if (error.code === "password_unchanged") return "unchanged";
    if (error.status === 422) return "invalid";
  }
  return "failed";
}

const accountMutation = useMutation({
  mutationFn: () => updateAccount({ ...form }),
  onSuccess(user) {
    auth.acceptUser(user);
    form.first_name = user.first_name ?? "";
    form.last_name = user.last_name ?? "";
    form.email = user.email ?? "";
    toasts.success({ title: t("settings.saved") });
  },
});
const languageMutation = useMutation({
  mutationFn: () => updateAccount({ preferred_locale: selectedLocale.value }),
  onSuccess(user) {
    auth.acceptUser(user);
    toasts.success({ title: t("settings.saved") });
  },
});
const passwordMutation = useMutation({
  mutationFn: () =>
    changePassword({
      current_password: passwords.current_password,
      new_password: passwords.new_password,
    }),
  async onSuccess() {
    clearPasswords();
    auth.signOut();
    await router.replace("/login");
    toasts.success({ title: t("settings.passwordChanged") });
  },
  onError(error) {
    passwordError.value = errorKey(error);
  },
});

/** Match confirmation before transmitting credentials; server enforces policy. */
function submitPassword(): void {
  passwordError.value = "";
  if (passwords.new_password !== passwords.confirm) {
    passwordError.value = "mismatch";
    return;
  }
  passwordMutation.mutate();
}
</script>

<template>
  <AppShell>
    <div class="workspace">
      <section class="settings-panel">
        <PanelHeading
          :title="t('settings.title')"
          :description="t('settings.description')"
          :icon="Settings"
          embedded
        />
        <TabsRoot
          :model-value="activeTab"
          :orientation="horizontalTabs ? 'horizontal' : 'vertical'"
          class="settings-layout"
          @update:model-value="selectTab"
        >
          <TabsList class="settings-tabs" :aria-label="t('settings.title')">
            <TabsTrigger
              v-for="tab in tabs"
              :key="tab.value"
              :value="tab.value"
              class="settings-tab"
            >
              <component :is="tab.icon" :size="18" aria-hidden="true" />
              {{ t(`settings.tabs.${tab.value}`) }}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="account" class="settings-content">
            <div class="settings-section-heading">
              <span class="settings-section-icon"
                ><UserRound :size="22" aria-hidden="true"
              /></span>
              <div>
                <h2>{{ t("settings.tabs.account") }}</h2>
                <p class="settings-description">
                  {{ t("settings.accountDescription") }}
                </p>
              </div>
            </div>
            <form class="tf-form" @submit.prevent="accountMutation.mutate()">
              <div class="settings-login">
                <span>{{ t("settings.username") }}</span>
                <strong>{{ auth.user?.username }}</strong>
                <LockKeyhole :size="15" aria-hidden="true" />
              </div>
              <fieldset
                class="settings-fields"
                :disabled="accountMutation.isPending.value"
              >
                <div class="form-grid form-grid--two">
                  <label class="field"
                    ><span>{{ t("settings.firstName") }}</span>
                    <input
                      v-model="form.first_name"
                      maxlength="150"
                      autocomplete="given-name"
                    />
                  </label>
                  <label class="field"
                    ><span>{{ t("settings.lastName") }}</span>
                    <input
                      v-model="form.last_name"
                      maxlength="150"
                      autocomplete="family-name"
                    />
                  </label>
                </div>
                <label class="field"
                  ><span>{{ t("settings.email") }}</span>
                  <input
                    v-model="form.email"
                    type="email"
                    maxlength="254"
                    autocomplete="email"
                    aria-describedby="email-hint"
                  />
                  <small id="email-hint">{{ t("settings.emailHint") }}</small>
                </label>
              </fieldset>
              <p
                v-if="accountMutation.error.value"
                class="settings-error"
                role="alert"
              >
                {{ t(`settings.${errorKey(accountMutation.error.value)}`) }}
              </p>
              <button
                class="button button--primary settings-save"
                :disabled="accountMutation.isPending.value"
              >
                {{
                  t(
                    accountMutation.isPending.value
                      ? "settings.saving"
                      : "settings.save",
                  )
                }}
              </button>
            </form>
          </TabsContent>

          <TabsContent value="interface" class="settings-content">
            <div class="settings-section-heading">
              <span class="settings-section-icon"
                ><Languages :size="22" aria-hidden="true"
              /></span>
              <div>
                <h2>{{ t("settings.tabs.interface") }}</h2>
                <p class="settings-description">
                  {{ t("settings.interfaceDescription") }}
                </p>
              </div>
            </div>
            <form class="tf-form" @submit.prevent="languageMutation.mutate()">
              <fieldset
                class="settings-fields"
                :disabled="languageMutation.isPending.value"
              >
                <legend class="settings-field-label">
                  {{ t("settings.language") }}
                </legend>
                <div class="settings-languages">
                  <label
                    v-for="language in [
                      { value: 'en', label: 'English', sample: 'Aa' },
                      { value: 'ru', label: 'Русский', sample: 'Аа' },
                    ]"
                    :key="language.value"
                    class="settings-language"
                  >
                    <input
                      v-model="selectedLocale"
                      type="radio"
                      name="language"
                      :value="language.value"
                      class="sr-only"
                    />
                    <span class="settings-language-sample" aria-hidden="true">{{
                      language.sample
                    }}</span>
                    <span class="settings-language-name">{{
                      language.label
                    }}</span>
                    <Check
                      class="settings-language-check"
                      :size="16"
                      aria-hidden="true"
                    />
                  </label>
                </div>
              </fieldset>
              <p
                v-if="languageMutation.error.value"
                class="settings-error"
                role="alert"
              >
                {{ t(`settings.${errorKey(languageMutation.error.value)}`) }}
              </p>
              <button
                class="button button--primary settings-save"
                :disabled="languageMutation.isPending.value"
              >
                {{
                  t(
                    languageMutation.isPending.value
                      ? "settings.saving"
                      : "settings.save",
                  )
                }}
              </button>
            </form>
          </TabsContent>

          <TabsContent value="security" class="settings-content">
            <div class="settings-section-heading">
              <span class="settings-section-icon"
                ><ShieldCheck :size="22" aria-hidden="true"
              /></span>
              <div>
                <h2>{{ t("settings.tabs.security") }}</h2>
                <p class="settings-description">
                  {{ t("settings.securityDescription") }}
                </p>
              </div>
            </div>
            <form class="tf-form" @submit.prevent="submitPassword">
              <fieldset
                class="settings-fields"
                :disabled="passwordMutation.isPending.value"
              >
                <input
                  class="sr-only"
                  :value="auth.user?.username"
                  autocomplete="username"
                  readonly
                  tabindex="-1"
                  :aria-label="t('settings.username')"
                />
                <label class="field"
                  ><span>{{ t("settings.currentPassword") }}</span>
                  <input
                    v-model="passwords.current_password"
                    type="password"
                    required
                    maxlength="128"
                    autocomplete="current-password"
                  />
                </label>
                <label class="field"
                  ><span>{{ t("settings.newPassword") }}</span>
                  <input
                    v-model="passwords.new_password"
                    type="password"
                    required
                    minlength="12"
                    maxlength="128"
                    autocomplete="new-password"
                    aria-describedby="password-hint"
                  />
                  <small id="password-hint">{{
                    t("settings.passwordHint")
                  }}</small>
                </label>
                <label class="field"
                  ><span>{{ t("settings.confirmPassword") }}</span>
                  <input
                    v-model="passwords.confirm"
                    type="password"
                    required
                    minlength="12"
                    maxlength="128"
                    autocomplete="new-password"
                  />
                </label>
              </fieldset>
              <p class="settings-notice">{{ t("settings.signOutWarning") }}</p>
              <p v-if="passwordError" class="settings-error" role="alert">
                {{ t(`settings.${passwordError}`) }}
              </p>
              <button
                class="button button--primary settings-save"
                :disabled="passwordMutation.isPending.value"
              >
                {{
                  t(
                    passwordMutation.isPending.value
                      ? "settings.saving"
                      : "settings.changePassword",
                  )
                }}
              </button>
            </form>
          </TabsContent>
        </TabsRoot>
      </section>
    </div>
  </AppShell>
</template>

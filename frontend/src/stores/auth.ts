import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { setLocale } from "@/i18n";

import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";
import {
  clearTokens,
  getTokens,
  setTokens,
  type TokenPair,
} from "@/api/tokens";

type User = components["schemas"]["UserResponse"];
type AuthStatus = "idle" | "loading" | "authenticated" | "anonymous";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const status = ref<AuthStatus>("idle");
  let bootstrapRequest: Promise<void> | null = null;

  const isAuthenticated = computed(
    () => status.value === "authenticated" && user.value !== null,
  );

  /** Keep account metadata and the persisted interface language together. */
  function acceptUser(next: User): void {
    user.value = next;
    if (next.preferred_locale === "en" || next.preferred_locale === "ru") {
      setLocale(next.preferred_locale);
    }
  }

  async function loadUser(): Promise<User> {
    const { data, error, response } = await api.GET("/api/v1/auth/me");
    if (data === undefined) {
      throw toApiError(error, response);
    }
    return data;
  }

  async function login(username: string, password: string): Promise<void> {
    status.value = "loading";
    const { data, error, response } = await api.POST("/api/v1/auth/token", {
      body: { username, password, scope: "" },
      bodySerializer(body) {
        return new URLSearchParams({
          username: body.username,
          password: body.password,
          scope: body.scope,
        }).toString();
      },
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });
    if (data === undefined) {
      status.value = "anonymous";
      throw toApiError(error, response);
    }

    setTokens(data as TokenPair);
    try {
      acceptUser(await loadUser());
      status.value = "authenticated";
    } catch (error: unknown) {
      signOut();
      throw error;
    }
  }

  async function bootstrap(): Promise<void> {
    if (bootstrapRequest !== null) {
      return bootstrapRequest;
    }
    if (status.value !== "idle") {
      return;
    }

    bootstrapRequest = (async () => {
      if (getTokens() === null) {
        status.value = "anonymous";
        return;
      }

      status.value = "loading";
      try {
        acceptUser(await loadUser());
        status.value = "authenticated";
      } catch {
        signOut();
      }
    })().finally(() => {
      bootstrapRequest = null;
    });
    return bootstrapRequest;
  }

  function signOut(): void {
    clearTokens();
    user.value = null;
    status.value = "anonymous";
  }

  return {
    acceptUser,
    bootstrap,
    isAuthenticated,
    login,
    signOut,
    status,
    user,
  };
});

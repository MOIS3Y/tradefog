import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { reloadTokens, setTokens } from "@/api/tokens";
import { useAuthStore } from "@/stores/auth";

const tokenPair = {
  access_token: "access-token",
  refresh_token: "refresh-token",
  token_type: "bearer",
};

const user = {
  id: 7,
  username: "trader",
  is_staff: false,
  is_active: true,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function requestUrl(input: RequestInfo | URL): string {
  return input instanceof Request ? input.url : String(input);
}

beforeEach(() => {
  window.localStorage.clear();
  reloadTokens();
  setActivePinia(createPinia());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("authentication flow", () => {
  it("exchanges credentials, loads the user, and clears the session", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/token")) {
        const request = input as Request;
        expect(await request.text()).toContain("username=trader");
        return jsonResponse(tokenPair);
      }

      expect((input as Request).headers.get("Authorization")).toBe(
        "Bearer access-token",
      );
      return jsonResponse(user);
    });
    vi.stubGlobal("fetch", fetchMock);

    const auth = useAuthStore();
    await auth.login("trader", "correct-password");

    expect(auth.isAuthenticated).toBe(true);
    expect(auth.user).toEqual(user);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    auth.signOut();
    expect(auth.isAuthenticated).toBe(false);
    expect(window.localStorage).toHaveLength(0);
  });

  it("renews an expired access token and retries the user request", async () => {
    setTokens({
      access_token: "expired-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
    });
    let userRequests = 0;

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input);
        if (url.endsWith("/api/v1/auth/refresh")) {
          expect(init?.body).toContain("refresh-token");
          return jsonResponse(tokenPair);
        }

        userRequests += 1;
        const authorization = (input as Request).headers.get("Authorization");
        if (userRequests === 1) {
          expect(authorization).toBe("Bearer expired-token");
          return jsonResponse({ detail: "expired" }, 401);
        }

        expect(authorization).toBe("Bearer access-token");
        return jsonResponse(user);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const auth = useAuthStore();
    await auth.bootstrap();

    expect(auth.isAuthenticated).toBe(true);
    expect(auth.user).toEqual(user);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});

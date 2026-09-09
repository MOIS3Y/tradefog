import createClient from "openapi-fetch";

import type { paths } from "@/api/schema";
import {
  clearTokens,
  getTokens,
  setTokens,
  type TokenPair,
} from "@/api/tokens";

const refreshPath = "/api/v1/auth/refresh";
const tokenPath = "/api/v1/auth/token";

let refreshRequest: Promise<boolean> | null = null;
let authenticationFailureHandler: (() => void) | null = null;

function isAuthenticationRequest(request: Request): boolean {
  const path = new URL(request.url).pathname;
  return path === refreshPath || path === tokenPath;
}

function withAccessToken(request: Request): Request {
  const tokens = getTokens();
  if (tokens === null) {
    return request;
  }

  const headers = new Headers(request.headers);
  headers.set("Authorization", `Bearer ${tokens.access_token}`);
  return new Request(request, { headers });
}

async function renewTokens(): Promise<boolean> {
  const tokens = getTokens();
  if (tokens === null) {
    return false;
  }

  const response = await fetch(refreshPath, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!response.ok) {
    clearTokens();
    authenticationFailureHandler?.();
    return false;
  }

  const nextTokens = (await response.json()) as TokenPair;
  setTokens(nextTokens);
  return true;
}

export async function authenticatedFetch(request: Request): Promise<Response> {
  const original = request.clone();
  const response = await fetch(withAccessToken(request));
  if (response.status !== 401 || isAuthenticationRequest(original)) {
    return response;
  }

  refreshRequest ??= renewTokens().finally(() => {
    refreshRequest = null;
  });
  if (!(await refreshRequest)) {
    return response;
  }

  return fetch(withAccessToken(original));
}

export function setAuthenticationFailureHandler(
  handler: (() => void) | null,
): void {
  authenticationFailureHandler = handler;
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: authenticatedFetch,
});

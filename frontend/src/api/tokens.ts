export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

const storageKey = "tradefog.auth.tokens";
let currentTokens: TokenPair | null = readStoredTokens();

function isTokenPair(value: unknown): value is TokenPair {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Partial<TokenPair>;
  return (
    typeof candidate.access_token === "string" &&
    typeof candidate.refresh_token === "string" &&
    typeof candidate.token_type === "string"
  );
}

function readStoredTokens(): TokenPair | null {
  if (typeof window === "undefined") {
    return null;
  }

  const stored = window.localStorage.getItem(storageKey);
  if (stored === null) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(stored);
    return isTokenPair(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function getTokens(): TokenPair | null {
  return currentTokens;
}

export function setTokens(tokens: TokenPair): void {
  currentTokens = tokens;
  window.localStorage.setItem(storageKey, JSON.stringify(tokens));
}

export function clearTokens(): void {
  currentTokens = null;
  window.localStorage.removeItem(storageKey);
}

export function reloadTokens(): void {
  currentTokens = readStoredTokens();
}

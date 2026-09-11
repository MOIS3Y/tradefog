/** Account settings use the authenticated self-service endpoints only. */
import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";

export type UserPatch = components["schemas"]["UserPatch"];
export type PasswordChange = components["schemas"]["PasswordChange"];

/** Return authoritative metadata after saving a partial account update. */
export async function updateAccount(body: UserPatch) {
  const { data, error, response } = await api.PATCH("/api/v1/auth/me", {
    body,
  });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

/** Replace credentials; success deliberately returns no renewable tokens. */
export async function changePassword(body: PasswordChange): Promise<void> {
  const { error, response } = await api.POST("/api/v1/auth/password", { body });
  if (!response.ok) throw toApiError(error, response);
}

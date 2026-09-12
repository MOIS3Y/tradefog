/** Typed API access for the owner-scoped trade journal workspace. */

import { api, authenticatedFetch } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components, paths } from "@/api/schema";
import type { Page } from "@/api/pagination";

export type Trade = components["schemas"]["TradeResponse"];
export type TradeCreate = components["schemas"]["TradeCreate"];
export type TradePatch = components["schemas"]["TradePatch"];
export type TradeStatus = components["schemas"]["TradeStatus"];
export type Direction = components["schemas"]["Direction"];
export type ChecklistWrite = components["schemas"]["ChecklistWrite"];
export type Checklist = components["schemas"]["ChecklistResponse"];
export type DirectionalValue = components["schemas"]["DirectionalValue"];
export type Plan = components["schemas"]["TradePlanResponse"];
export type PlanInput = components["schemas"]["TradePlanRequest-Input"];
export type PlanningContext =
  components["schemas"]["TradePlanningContextResponse"];
export type ATR = components["schemas"]["ATRResponse"];
export type Attachment = components["schemas"]["AttachmentResponse"];
export type TradeClose = components["schemas"]["TradeClose"];

export type TradeListItem = components["schemas"]["TradeListItem"];
export type TradeListParams = NonNullable<
  paths["/api/v1/trades"]["get"]["parameters"]["query"]
>;

export async function listTrades(
  query: TradeListParams = {},
  profileId?: number,
): Promise<Page<TradeListItem>> {
  const { profile_id: filter, ...scopedQuery } = query;
  const { data, error, response } =
    profileId === undefined
      ? await api.GET("/api/v1/trades", { params: { query } })
      : await api.GET("/api/v1/profiles/{profile_id}/trades", {
          params: { path: { profile_id: profileId }, query: scopedQuery },
        });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function getTrade(profileId: number, id: number): Promise<Trade> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}",
    {
      params: { path: { profile_id: profileId, trade_id: id } },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function createTrade(
  profileId: number,
  input: TradeCreate,
): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/trades",
    {
      params: { path: { profile_id: profileId } },
      body: input,
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateTrade(
  profileId: number,
  id: number,
  input: TradePatch,
): Promise<Trade> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}",
    { params: { path: { profile_id: profileId, trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function deleteTrade(
  profileId: number,
  id: number,
): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}",
    {
      params: { path: { profile_id: profileId, trade_id: id } },
    },
  );
  if (!response.ok) throw toApiError(error, response);
}

export async function saveChecklist(
  profileId: number,
  id: number,
  input: ChecklistWrite,
): Promise<Checklist> {
  const { data, error, response } = await api.PUT(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/checklist",
    { params: { path: { profile_id: profileId, trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function refreshATR(
  profileId: number,
  id: number,
  value?: string,
  observedSessionRange?: string,
): Promise<ATR> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/atr",
    {
      params: { path: { profile_id: profileId, trade_id: id } },
      body: {
        value: value || null,
        observed_session_range: observedSessionRange || null,
        stale: false,
      },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function previewPlan(
  profileId: number,
  id: number,
  input: PlanInput,
): Promise<Plan> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/plan/preview",
    { params: { path: { profile_id: profileId, trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function getPlanningContext(
  profileId: number,
  id: number,
): Promise<PlanningContext> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/planning-context",
    { params: { path: { profile_id: profileId, trade_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function savePlan(
  profileId: number,
  id: number,
  input: components["schemas"]["TradePlanSave"],
): Promise<Trade> {
  const { data, error, response } = await api.PUT(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/plan",
    { params: { path: { profile_id: profileId, trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function submitTrade(
  profileId: number,
  id: number,
  status: "pending_entry" | "open",
): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/submit",
    {
      params: { path: { profile_id: profileId, trade_id: id } },
      body: { status },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function openTrade(profileId: number, id: number): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/open",
    { params: { path: { profile_id: profileId, trade_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function cancelTrade(
  profileId: number,
  id: number,
): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/cancel",
    { params: { path: { profile_id: profileId, trade_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function closeTrade(
  profileId: number,
  id: number,
  input: TradeClose,
): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/close",
    { params: { path: { profile_id: profileId, trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function setReviewed(
  profileId: number,
  id: number,
  completed: boolean,
): Promise<Trade> {
  const { data, error, response } = await api.PUT(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/review",
    {
      params: { path: { profile_id: profileId, trade_id: id } },
      body: { completed },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function listAttachments(
  profileId: number,
  id: number,
): Promise<Attachment[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/attachments",
    { params: { path: { profile_id: profileId, trade_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function uploadAttachment(
  profileId: number,
  id: number,
  upload: File,
): Promise<Attachment> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/attachments",
    {
      params: { path: { profile_id: profileId, trade_id: id } },
      body: { upload } as never,
      bodySerializer(body) {
        const form = new FormData();
        form.set("upload", (body as unknown as { upload: File }).upload);
        return form;
      },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function deleteAttachment(
  profileId: number,
  tradeId: number,
  id: number,
): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/profiles/{profile_id}/trades/{trade_id}/attachments/{attachment_id}",
    {
      params: {
        path: { profile_id: profileId, trade_id: tradeId, attachment_id: id },
      },
    },
  );
  if (!response.ok) throw toApiError(error, response);
}

export async function fetchAttachmentContent(item: Attachment): Promise<Blob> {
  const response = await authenticatedFetch(
    new Request(new URL(item.content_url, window.location.origin)),
  );
  if (!response.ok) throw toApiError(undefined, response);
  return response.blob();
}

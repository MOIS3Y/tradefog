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
): Promise<Page<TradeListItem>> {
  const { data, error, response } = await api.GET("/api/v1/trades", {
    params: { query },
  });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function getTrade(id: number): Promise<Trade> {
  const { data, error, response } = await api.GET("/api/v1/trades/{trade_id}", {
    params: { path: { trade_id: id } },
  });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function createTrade(input: TradeCreate): Promise<Trade> {
  const { data, error, response } = await api.POST("/api/v1/trades", {
    body: input,
  });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateTrade(
  id: number,
  input: TradePatch,
): Promise<Trade> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/trades/{trade_id}",
    { params: { path: { trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function deleteTrade(id: number): Promise<void> {
  const { error, response } = await api.DELETE("/api/v1/trades/{trade_id}", {
    params: { path: { trade_id: id } },
  });
  if (!response.ok) throw toApiError(error, response);
}

export async function saveChecklist(
  id: number,
  input: ChecklistWrite,
): Promise<Checklist> {
  const { data, error, response } = await api.PUT(
    "/api/v1/trades/{trade_id}/checklist",
    { params: { path: { trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function refreshATR(
  id: number,
  value?: string,
  observedSessionRange?: string,
): Promise<ATR> {
  const { data, error, response } = await api.POST(
    "/api/v1/trades/{trade_id}/atr",
    {
      params: { path: { trade_id: id } },
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

export async function previewPlan(id: number, input: PlanInput): Promise<Plan> {
  const { data, error, response } = await api.POST(
    "/api/v1/trades/{trade_id}/plan",
    { params: { path: { trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function getPlanningContext(id: number): Promise<PlanningContext> {
  const { data, error, response } = await api.GET(
    "/api/v1/trades/{trade_id}/plan-context",
    { params: { path: { trade_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function savePlan(id: number, input: PlanInput): Promise<Trade> {
  const { data, error, response } = await api.PUT(
    "/api/v1/trades/{trade_id}/plan",
    { params: { path: { trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function submitTrade(
  id: number,
  status: "pending_entry" | "open",
): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/trades/{trade_id}/submit",
    { params: { path: { trade_id: id } }, body: { status } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function openTrade(id: number): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/trades/{trade_id}/open",
    { params: { path: { trade_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function cancelTrade(id: number): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/trades/{trade_id}/cancel",
    { params: { path: { trade_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function closeTrade(
  id: number,
  input: TradeClose,
): Promise<Trade> {
  const { data, error, response } = await api.POST(
    "/api/v1/trades/{trade_id}/close",
    { params: { path: { trade_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function setReviewed(
  id: number,
  completed: boolean,
): Promise<Trade> {
  const { data, error, response } = await api.PUT(
    "/api/v1/trades/{trade_id}/review",
    { params: { path: { trade_id: id } }, body: { completed } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function listAttachments(id: number): Promise<Attachment[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/trades/{trade_id}/attachments",
    { params: { path: { trade_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function uploadAttachment(
  id: number,
  upload: File,
): Promise<Attachment> {
  const { data, error, response } = await api.POST(
    "/api/v1/trades/{trade_id}/attachments",
    {
      params: { path: { trade_id: id } },
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

export async function deleteAttachment(id: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/attachments/{attachment_id}",
    { params: { path: { attachment_id: id } } },
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

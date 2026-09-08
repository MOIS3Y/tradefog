interface ErrorDetail {
  code?: string;
  message?: string;
}

interface ErrorEnvelope {
  detail?: ErrorDetail | ValidationDetail[] | string;
}

interface ValidationDetail {
  loc?: Array<number | string>;
  msg?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function toApiError(error: unknown, response?: Response): ApiError {
  const status = response?.status ?? 0;
  if (typeof error !== "object" || error === null) {
    return new ApiError(status, "request_failed", "Request failed");
  }

  const envelope = error as ErrorEnvelope;
  if (typeof envelope.detail === "string") {
    return new ApiError(status, "request_failed", envelope.detail);
  }

  if (Array.isArray(envelope.detail)) {
    const first = envelope.detail[0];
    return new ApiError(
      status,
      "validation_error",
      first?.msg ?? "Request validation failed",
    );
  }

  return new ApiError(
    status,
    envelope.detail?.code ?? "request_failed",
    envelope.detail?.message ?? "Request failed",
  );
}

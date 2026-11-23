import { getApiBaseUrl } from "./config";
import type {
  ApiErrorPayload,
  ValidationIssue,
} from "@/types/api/errors";

export class HttpError extends Error {
  readonly status: number;
  readonly payload: unknown;
  readonly apiError: ApiErrorPayload | undefined;

  constructor(status: number, payload: unknown, statusText: string) {
    const apiError = getApiErrorPayload(payload);
    super(getErrorMessage(apiError, payload, statusText));
    this.name = "HttpError";
    this.status = status;
    this.payload = payload;
    this.apiError = apiError;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isValidationIssue(value: unknown): value is ValidationIssue {
  if (!isRecord(value)) return false;

  return (
    typeof value.type === "string" &&
    typeof value.msg === "string" &&
    Array.isArray(value.loc) &&
    value.loc.every(
      (part) => typeof part === "string" || typeof part === "number",
    ) &&
    (value.ctx === undefined || isRecord(value.ctx))
  );
}

function getApiErrorPayload(value: unknown): ApiErrorPayload | undefined {
  if (!isRecord(value)) return undefined;

  if (typeof value.detail === "string") {
    return { detail: value.detail };
  }

  if (
    Array.isArray(value.detail) &&
    value.detail.every(isValidationIssue)
  ) {
    return { detail: value.detail };
  }

  return undefined;
}

function getErrorMessage(
  apiError: ApiErrorPayload | undefined,
  payload: unknown,
  statusText: string,
): string {
  if (apiError) {
    const { detail } = apiError;
    if (typeof detail === "string") return detail;
    return detail.map((issue) => issue.msg).join("; ");
  }

  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  return statusText || "HTTP request failed";
}

async function readPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;

  const contentType = (response.headers.get("content-type") ?? "").toLowerCase();
  if (contentType.includes("application/json") || contentType.includes("+json")) {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }

  return text;
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const normalizedPath = path.replace(/^\/+/, "");
  const url = `${getApiBaseUrl()}/${normalizedPath}`;
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetch(url, { ...init, headers });
  const payload = await readPayload(response);

  if (!response.ok) {
    throw new HttpError(response.status, payload, response.statusText);
  }

  return payload as T;
}

export interface ManualHttpError {
  detail: string;
}

export interface ValidationIssue {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface ValidationHttpError {
  detail: ValidationIssue[];
}

export type ApiErrorPayload = ManualHttpError | ValidationHttpError;

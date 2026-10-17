import type { components } from "./generated/schema";
import { assertCurrentSession, expireSession, sessionExpiredMessage } from "../utils/session";
export type PeriodPreview = components["schemas"]["RetrospectivePreview"];
export type PeriodResult = components["schemas"]["RetrospectiveResult"];

export function periodFilters(params: URLSearchParams) {
  const filters = new URLSearchParams();
  for (const name of ["date_from", "date_to", "date_field", "source", "type"]) {
    const value = params.get(name);
    if (value) filters.set(name, value);
  }
  if (!filters.has("date_field")) filters.set("date_field", "event_at");
  return filters;
}
async function request<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("Please log in to continue.");
  signal?.throwIfAborted();
  const response = await fetch(`/api/retrospectives${path}`, { signal, method: body ? "POST" : "GET",
    headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  if (response.status === 401) { expireSession(token); throw new Error(sessionExpiredMessage); }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const messages: Record<string, string> = {
      RETROSPECTIVE_PREVIEW_CHANGED: "The period, records or permissions changed. Review the period again.",
      RETROSPECTIVE_NO_EVIDENCE: "No eligible passages remain for this period.",
      ANSWER_DISABLED: "Answer generation is disabled on this server.",
      EMBEDDING_BUDGET_EXHAUSTED: "The AI budget is exhausted.",
      ANSWER_REQUEST_ALREADY_USED: "This request was already attempted and will not be repeated.",
    };
    throw new Error((messages[error.detail] ?? (response.status === 422 ? "Choose valid dates within 92 days." : "The retrospective could not finish."))
      + (body ? " A request already sent may have been charged. No automatic retry will be made." : " No AI request was made by this preview."));
  }
  const value = await response.json(); signal?.throwIfAborted(); assertCurrentSession(token); return value as T;
}
export const previewPeriod = (params: URLSearchParams, signal?: AbortSignal) => request<PeriodPreview>(`/preview?${periodFilters(params)}`, signal);
export const summarizePeriod = (preview: PeriodPreview, signal: AbortSignal) => request<PeriodResult>("", signal, {
  ...preview.scope, preview_digest: preview.preview_digest, request_id: crypto.randomUUID().replaceAll("-", ""), confirm_external_ai: true,
});

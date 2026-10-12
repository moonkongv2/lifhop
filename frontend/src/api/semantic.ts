import type { components } from "./generated/schema";
import { assertCurrentSession, expireSession, sessionExpiredMessage } from "../utils/session";

export type SemanticCoverage = components["schemas"]["SemanticCoverage"];
export type SemanticResponse = components["schemas"]["SemanticResponse"];
export type SemanticLocations = components["schemas"]["SemanticLocations"];
type Passage = components["schemas"]["PassageResponse"];

const messages: Record<string, string> = {
  EMBEDDING_BUSY: "Another AI request is running. Submit again when it finishes.",
  EMBEDDING_BUDGET_EXHAUSTED: "The AI budget is exhausted. No automatic retry will be made.",
  EMBEDDING_DISABLED: "Semantic search is disabled.",
  EMBEDDING_KEY_MISSING: "Semantic search is not configured.",
  PROVIDER_TIMEOUT_OR_NETWORK: "The AI request timed out or lost its connection. It may have been charged. Submit again only if you want another request.",
  SEMANTIC_REQUEST_ALREADY_USED: "This request was already attempted. It will not be sent again automatically.",
  SEMANTIC_CONTEXT_CHANGED: "Your records or permissions changed. A completed AI request may have been charged. Review the filters and submit again.",
};

async function request<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("Please log in to continue.");
  const response = await fetch(`/api/semantic${path}`, { signal, method: body ? "POST" : "GET",
    headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  if (response.status === 401) { expireSession(token); throw new Error(sessionExpiredMessage); }
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new Error(messages[value.detail] ?? (response.status === 404 ? "This slice is unavailable or has changed. Return to search."
      : response.status === 422 ? "Enter a question and valid filters." : "Semantic search could not finish. No automatic retry will be made; a dispatched request may have been charged."));
  }
  const data = await response.json();
  assertCurrentSession(token);
  return data as T;
}

export function semanticFilters(params: URLSearchParams) {
  const query = new URLSearchParams();
  for (const key of ["source", "source_state", "type", "date_field", "date_from", "date_to"]) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  return query;
}
export const fetchSemanticStatus = (params: URLSearchParams, signal?: AbortSignal) => request<SemanticCoverage>(`/status?${semanticFilters(params)}`, signal);
export function searchSemantic(params: URLSearchParams, signal?: AbortSignal) {
  const filters: Record<string, string> = {};
  semanticFilters(params).forEach((value, key) => { filters[key] = value; });
  return request<SemanticResponse>("/search", signal, { ...filters,
    q: params.get("q") ?? "", request_id: crypto.randomUUID().replaceAll("-", ""), confirm_external_ai: true });
}
export const fetchSemanticSlice = (id: string, signal?: AbortSignal) => request<Passage>(`/slices/${encodeURIComponent(id)}`, signal);
export function fetchSemanticLocations(id: number, params: URLSearchParams, offset: number, signal?: AbortSignal) {
  const query = semanticFilters(params); query.set("offset", String(offset));
  return request<SemanticLocations>(`/slices/${id}/locations?${query}`, signal);
}

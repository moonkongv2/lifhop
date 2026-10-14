import type { components } from "./generated/schema";
import { assertCurrentSession, expireSession, sessionExpiredMessage } from "../utils/session";

export type AnswerResponse = components["schemas"]["AnswerResponse"];
export type AnswerStatus = components["schemas"]["AnswerStatus"];

const messages: Record<string,string> = {
  ANSWER_DISABLED: "Answer generation is not enabled for this server.",
  EMBEDDING_BUDGET_EXHAUSTED: "The AI budget is exhausted.",
  EMBEDDING_BUSY: "Another AI request is running. Submit again later.",
  ANSWER_REQUEST_ALREADY_USED: "This answer request was already attempted.",
  ANSWER_CONTEXT_CHANGED: "The selected records or permissions changed. A sent request may have been charged.",
  ANSWER_SLICE_UNAVAILABLE: "A selected passage is no longer available.",
  PROVIDER_TIMEOUT_OR_NETWORK: "The request timed out or lost its connection. It may have been charged.",
};

async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("Please log in to continue.");
  const response = await fetch(`/api/answers${path}`, { method: body ? "POST" : "GET", signal,
    headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  if (response.status === 401) { expireSession(token); throw new Error(sessionExpiredMessage); }
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new Error(messages[value.detail] ?? "The answer request could not finish. A sent request may have been charged.");
  }
  const data = await response.json();
  assertCurrentSession(token);
  return data as T;
}

export const fetchAnswerStatus = (signal?: AbortSignal) => request<AnswerStatus>("/status", undefined, signal);
export const requestAnswer = (q: string, ids: number[]) => request<AnswerResponse>("", {
  q, embedding_ids: ids, request_id: crypto.randomUUID().replaceAll("-", ""), confirm_external_ai: true,
});

import type { components } from "./generated/schema";
import { assertCurrentSession, expireSession, getAccessToken, sessionExpiredMessage } from "../utils/session";
export type Conversation = components["schemas"]["ConversationResponse"];
export type ConversationList = components["schemas"]["ConversationPage"];
export type Turn = components["schemas"]["TurnResponse"];
export type TurnInput = components["schemas"]["TurnCreate"];

async function request<T>(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  const token = getAccessToken();
  if (!token) throw new Error("Please log in to continue.");
  const response = await fetch(`/api/answer-conversations${path}`, { method, signal, cache: "no-store",
    headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  if (response.status === 401) { expireSession(token); throw new Error(sessionExpiredMessage); }
  assertCurrentSession(token);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(`${data.detail ?? "Conversation request failed"}. Refresh to see saved state. A sent AI request may have been charged. No automatic retry.`);
  }
  if (response.status === 204) return undefined as T;
  const value = await response.json();
  assertCurrentSession(token);
  return value as T;
}
export const fetchConversations = (cursor?: string, signal?: AbortSignal) => request<ConversationList>(cursor ? `?cursor=${encodeURIComponent(cursor)}` : "", "GET", undefined, signal);
export const fetchConversation = (id: string, signal?: AbortSignal, before?: number) => request<Conversation>(`/${id}${before ? `?before=${before}` : ""}`, "GET", undefined, signal);
export const createConversation = (params: URLSearchParams, signal?: AbortSignal) => {
  const filters: Record<string,string> = {};
  for (const key of ["source", "type", "date_field", "date_from", "date_to"]) if (params.get(key)) filters[key] = params.get(key)!;
  return request<Conversation>("", "POST", filters, signal);
};
export const claimTurn = (id: string, input: TurnInput, signal?: AbortSignal) => request<Conversation>(`/${id}/turns`, "POST", input, signal);
export const conversationStage = (id: string, turn: Pick<Turn, "id" | "request_id">, stage: string, signal?: AbortSignal) => request<Conversation>(`/${id}/turns/${turn.id}/${stage}`, "POST", { request_id: turn.request_id, confirm_external_ai: true }, signal);
export const changeConversation = (value: Conversation, action: "close" | "reopen") => request<Conversation>(`/${value.id}/${action}`, "POST", { expected_revision: value.revision });
export const deleteConversation = (id: string) => request<void>(`/${id}`, "DELETE");

export async function runTurn(initial: Conversation, signal: AbortSignal, progress: (value: Conversation) => void) {
  let current = initial;
  const id = initial.turns.at(-1)!.id;
  const get = () => current.turns.find(t => t.id === id)!;
  const step = async (name: string) => {
    signal.throwIfAborted();
    current = await conversationStage(current.id, get(), name, signal);
    signal.throwIfAborted();
    progress(current);
  };
  await step("plan");
  if (get().state === "planned") await step(get().branch === "reuse" ? "evidence" : "search");
  if (get().state === "ready") await step("answer");
  return current;
}

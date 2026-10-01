import type { components } from "./generated/schema";

export type Entry = components["schemas"]["EntryResponse"];
export type EntryCreate = components["schemas"]["EntryCreate"];
export type EntryUpdate = components["schemas"]["EntryUpdate"];

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("Please log in to continue.");

  const response = await fetch(`/api/entries${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: "Your session has expired. Please log in again.",
      404: "Entry not found. It may have been deleted or you may not have access.",
    };
    if (response.status === 422) {
      let detail: unknown;
      try { detail = (await response.json()).detail; } catch { /* Use a safe fallback. */ }
      throw new Error(typeof detail === "string" ? detail : "Please check your input or search filters.");
    }
    throw new Error(messages[response.status] ?? `Request failed: ${response.status}. Please try again.`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const fetchEntries = () => request<Entry[]>("");
export const fetchEntry = (id: string) => request<Entry>(`/${id}`);
export const createEntry = (data: EntryCreate) =>
  request<Entry>("", { method: "POST", body: JSON.stringify(data) });
export const updateEntry = (id: string, data: EntryUpdate) =>
  request<Entry>(`/${id}`, { method: "PATCH", body: JSON.stringify(data) });
export const deleteEntry = (id: string) => request<void>(`/${id}`, { method: "DELETE" });

export type EntrySearch = components["schemas"]["EntrySearchResponse"];
export const fetchEntrySearch = (params: URLSearchParams, signal?: AbortSignal) => {
  const query = new URLSearchParams(params);
  query.set("limit", "20");
  return request<EntrySearch>(`/search?${query}`, { signal });
};

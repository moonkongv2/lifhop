import type { components } from "./generated/schema";

export type Entry = components["schemas"]["EntryResponse"];
export type EntryCreate = components["schemas"]["EntryCreate"];
export type EntryUpdate = components["schemas"]["EntryUpdate"];

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("로그인이 필요해.");

  const response = await fetch(`/api/entries${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: "로그인이 만료됐어. 다시 로그인해 줘.",
      404: "Entry를 찾을 수 없어. 삭제됐거나 접근 권한이 없을 수 있어.",
    };
    if (response.status === 422) {
      let detail: unknown;
      try { detail = (await response.json()).detail; } catch { /* Use a safe fallback. */ }
      throw new Error(typeof detail === "string" ? detail : "입력값이나 검색 조건을 확인해 줘.");
    }
    throw new Error(messages[response.status] ?? `요청 실패: ${response.status}. 다시 시도해 줘.`);
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

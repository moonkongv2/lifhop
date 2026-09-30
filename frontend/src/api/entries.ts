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
      422: "입력값을 확인해 줘. 제목은 공백만으로 작성할 수 없고, 255자 이하여야 해.",
    };
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

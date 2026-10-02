import type { components } from "./generated/schema";
import type { Entry } from "./entries";
export type Version = components["schemas"]["VersionResponse"];
export type Policy = components["schemas"]["PolicyResponse"];
export type Suppression = components["schemas"]["SuppressionResponse"];

export async function historyRequest<T>(path: string, data?: unknown, method = "GET"): Promise<T> {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("Please log in to continue.");
  const response = await fetch(`/api${path}`, {
    method, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    let detail: unknown;
    try { detail = (await response.json()).detail; } catch { /* Use a status fallback. */ }
    throw new Error(typeof detail === "string" ? detail : `Request failed: ${response.status}`);
  }
  return response.status === 204 ? undefined as T : response.json();
}
export const fetchVersions = (id: number) => historyRequest<Version[]>(`/entries/${id}/versions`);
export const chooseVersion = (id: number, version: number) => historyRequest<Entry>(`/entries/${id}/versions/${version}/select`, {}, "POST");
export const saveSettings = (id: number, settings: components["schemas"]["RecordSettings"]) => historyRequest<Entry>(`/entries/${id}/settings`, settings, "PATCH");
export const saveSourceState = (id: number, state: string) => historyRequest<Entry>(`/entries/${id}/source-state`, { state, confirmed: state === "deleted" }, "PATCH");

import type { components } from "./generated/schema";
import { assertCurrentSession, expireSession, sessionExpiredMessage } from "../utils/session";

export type Passage = components["schemas"]["PassageResponse"];
export type PassageSearch = components["schemas"]["PassageSearchResponse"];
export type PassageSnapshots = components["schemas"]["PassageSnapshotsResponse"];

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("Please log in to continue.");
  const response = await fetch(`/api/passages${path}`, { signal, cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
  if (response.status === 401) { expireSession(token); throw new Error(sessionExpiredMessage); }
  if (!response.ok) {
    if (response.status === 404 && path.startsWith("/citation?")) throw new Error("The cited original is unavailable. It may have been deleted from lifhop or you may no longer have access. No replacement text is shown.");
    if (response.status === 404) throw new Error("This passage is unavailable or has changed. Run your search again.");
    if (response.status === 503) throw new Error("Search could not finish within its limits. Narrow your query or try again.");
    throw new Error(response.status === 422 ? "Enter a query and valid search filters." : "Unable to load passages. Please try again.");
  }
  const data = await response.json();
  assertCurrentSession(token);
  return data as T;
}

function searchParams(params: URLSearchParams) {
  const query = new URLSearchParams(params);
  query.delete("mode");
  return query;
}

export function fetchPassages(params: URLSearchParams, signal?: AbortSignal) {
  const query = searchParams(params);
  query.set("limit", "20");
  return request<PassageSearch>(`/search?${query}`, signal);
}
export const fetchPassage = (id: string, signal?: AbortSignal) => request<Passage>(`/${encodeURIComponent(id)}`, signal);
export function fetchPassageSnapshots(id: number, params: URLSearchParams, offset: number, signal?: AbortSignal) {
  const query = searchParams(params);
  query.set("limit", "20"); query.set("offset", String(offset));
  return request<PassageSnapshots>(`/${id}/snapshots?${query}`, signal);
}

export function citationTarget(passage: Passage, returnTo: string, path = `/passages/${passage.id}`) {
  return `${path}?${new URLSearchParams({ returnTo, version_id: String(passage.version_id),
    field: passage.field, start: String(passage.start), end: String(passage.end), passage_hash: passage.passage_hash })}`;
}

export function fetchCitation(params: URLSearchParams, signal?: AbortSignal) {
  const anchor = new URLSearchParams();
  for (const key of ["version_id", "field", "start", "end", "passage_hash"]) anchor.set(key, params.get(key) ?? "");
  return request<components["schemas"]["CitationResponse"]>(`/citation?${anchor}`, signal);
}

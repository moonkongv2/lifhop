import { entryTarget, listTarget, resolveEntryContext } from "./entryNavigation";
import type { EntryListContext } from "./entryNavigation";
import type { components } from "../api/generated/schema";

export type RepositorySummary = components["schemas"]["GitHubRepositorySummary"];
export type RepositoryRecords = components["schemas"]["GitHubRecordsResponse"];
export type RepositoryDocuments = components["schemas"]["GitHubDocumentsResponse"];
export type RepositoryContext = { scope: string; tab: "commits" | "documents" | "unclassified";
  offset: number; doc_offset: number; snapshot_offset: number; path: string | null; outer: EntryListContext };
const base = "https://lifhop.invalid";
export function validDocumentPath(path: string) {
  return path.length > 0 && path.length <= 4096 && ![...path].some(char => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)
    && path.split("/").every(part => part !== "" && part !== "." && part !== "..");
}
export function repositoryContext(params: URLSearchParams): RepositoryContext | null {
  const scope = params.get("scope") ?? "";
  const tab = params.get("tab") ?? "commits";
  if (!/^repo:[1-9][0-9]{0,19}$/.test(scope) || !["commits", "documents", "unclassified"].includes(tab)) return null;
  const values = ["offset", "doc_offset", "snapshot_offset"].map(key => {
    const value = params.get(key) ?? "0";
    return /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : NaN;
  });
  const path = params.get("path");
  if (values.some(Number.isNaN) || (path !== null && !validDocumentPath(path))) return null;
  return { scope, tab: tab as RepositoryContext["tab"], offset: values[0], doc_offset: values[1],
    snapshot_offset: values[2], path, outer: resolveEntryContext(params.toString()) };
}
export function repositoryTarget(context: RepositoryContext): string {
  const params = new URLSearchParams({ scope: context.scope, tab: context.tab, returnTo: listTarget(context.outer) });
  for (const key of ["offset", "doc_offset", "snapshot_offset"] as const) if (context[key]) params.set(key, String(context[key]));
  if (context.path) params.set("path", context.path);
  return `/repositories/github?${params}`;
}
export function repositoryLink(scope: string, outer: EntryListContext): string {
  return repositoryTarget({scope, tab:"commits", offset:0, doc_offset:0, snapshot_offset:0, path:null, outer});
}
export function safeRepositoryContext(value: string | null): RepositoryContext | null {
  if (!value?.startsWith("/repositories/github?") || value.startsWith("//")) return null;
  try {
    const url = new URL(value, base);
    if (url.origin !== base || url.pathname !== "/repositories/github" || url.hash) return null;
    const context = repositoryContext(url.searchParams);
    return context?.tab === "documents" && !context.path ? null : context;
  } catch { return null; }
}
export function githubEntryTarget(id: number, context: RepositoryContext): string {
  return entryTarget(id, context.outer) + "&" + new URLSearchParams({ repositoryReturn: repositoryTarget(context) });
}
export function repositoryRecordsUrl(context: RepositoryContext): string {
  const params = new URLSearchParams({scope:context.scope, limit:"20"});
  if (context.tab === "documents") {
    params.set("path", context.path!); params.set("offset", String(context.snapshot_offset));
    return `/github-repositories/document-snapshots?${params}`;
  }
  params.set("kind", context.tab === "commits" ? "commit" : "unclassified");
  params.set("offset", String(context.offset));
  return `/github-repositories/records?${params}`;
}
export function eventDay(value: string | null) {
  return value ? new Intl.DateTimeFormat("en-US", {timeZone:"Asia/Seoul",dateStyle:"long"}).format(new Date(value)) : "Date unknown";
}

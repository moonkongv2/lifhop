import { entryTarget, listTarget, resolveEntryContext } from "./entryNavigation";
import type { EntryListContext } from "./entryNavigation";
import type { components } from "../api/generated/schema";

export type RepositorySummary = components["schemas"]["GitHubRepositorySummary"];
export type RepositoryRecords = components["schemas"]["GitHubRecordsResponse"];
export type RepositoryDocuments = components["schemas"]["GitHubDocumentsResponse"];
export type Discussions = components["schemas"]["GitHubDiscussionsResponse"];
export type Discussion = components["schemas"]["GitHubDiscussionSummary"];
export type DiscussionThread = components["schemas"]["GitHubThreadResponse"];
export type RepositoryContext = { scope: string; tab: "commits" | "documents" | "discussions" | "unclassified";
  offset: number; doc_offset: number; snapshot_offset: number; path: string | null; outer: EntryListContext;
  discussion_offset?: number; thread_offset?: number; thread_kind?: "pull_request" | "issue"; thread_id?: string;
  focus_entry_id?: number; discussion_kind?: "pull_request" | "issue"; discussion_state?: "open" | "closed" | "merged" | "unknown";
  discussion_from?: string; discussion_to?: string; unknown_date?: boolean };
const base = "https://lifhop.invalid";
export function validDocumentPath(path: string) {
  return path.length > 0 && path.length <= 4096 && ![...path].some(char => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)
    && path.split("/").every(part => part !== "" && part !== "." && part !== "..");
}
export function repositoryContext(params: URLSearchParams): RepositoryContext | null {
  const scope = params.get("scope") ?? "";
  const tab = params.get("tab") ?? "commits";
  if (!/^repo:[1-9][0-9]{0,19}$/.test(scope) || !["commits", "documents", "discussions", "unclassified"].includes(tab)) return null;
  const values = ["offset", "doc_offset", "snapshot_offset", "discussion_offset", "thread_offset"].map(key => {
    const value = params.get(key) ?? "0";
    return /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : NaN;
  });
  const path = params.get("path");
  if (values.some(Number.isNaN) || (path !== null && !validDocumentPath(path))) return null;
  const threadKind = params.get("thread_kind") ?? undefined;
  const threadId = params.get("thread_id") ?? undefined;
  const kind = params.get("discussion_kind") ?? undefined;
  const state = params.get("discussion_state") ?? undefined;
  const from = params.get("discussion_from") ?? undefined;
  const to = params.get("discussion_to") ?? undefined;
  const unknownDate = params.get("unknown_date") === "true";
  const focus = params.get("focus_entry_id");
  if ((threadKind && !["pull_request","issue"].includes(threadKind)) || (threadId && !/^[1-9][0-9]{0,19}$/.test(threadId))
    || (!!threadKind !== !!threadId) || (kind && !["pull_request","issue"].includes(kind))
    || (state && !["open","closed","merged","unknown"].includes(state))
    || (focus && (!/^[1-9][0-9]*$/.test(focus) || !Number.isSafeInteger(Number(focus)) || !threadId))) return null;
  for (const day of [from,to]) if (day && (!/^\d{4}-\d{2}-\d{2}$/.test(day) || Number.isNaN(Date.parse(day))
    || new Date(day).toISOString().slice(0,10) !== day || day === "9999-12-31")) return null;
  if ((from && to && from > to) || (unknownDate && (from || to))) return null;
  return { scope, tab: tab as RepositoryContext["tab"], offset: values[0], doc_offset: values[1],
    snapshot_offset: values[2], path, outer: resolveEntryContext(params.toString()), discussion_offset:values[3],
    thread_offset:values[4], thread_kind:threadKind as RepositoryContext["thread_kind"], thread_id:threadId,
    discussion_kind:kind as RepositoryContext["discussion_kind"], discussion_state:state as RepositoryContext["discussion_state"],
    discussion_from:from, discussion_to:to, unknown_date:unknownDate, focus_entry_id:focus ? Number(focus) : undefined };
}
export function repositoryTarget(context: RepositoryContext): string {
  const params = new URLSearchParams({ scope: context.scope, tab: context.tab, returnTo: listTarget(context.outer) });
  for (const key of ["offset", "doc_offset", "snapshot_offset", "discussion_offset", "thread_offset", "focus_entry_id"] as const) if (context[key]) params.set(key, String(context[key]));
  if (context.path) params.set("path", context.path);
  for (const key of ["thread_kind","thread_id","discussion_kind","discussion_state","discussion_from","discussion_to"] as const) if (context[key]) params.set(key, context[key]);
  if (context.unknown_date) params.set("unknown_date", "true");
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
  if (context.tab === "discussions") {
    if (context.thread_kind && context.thread_id) {
      params.set("offset", String(context.thread_offset ?? 0));
      if (context.focus_entry_id) params.set("focus_entry_id", String(context.focus_entry_id));
      return `/github-repositories/discussions/${context.thread_kind}/${context.thread_id}?${params}`;
    }
    params.set("offset", String(context.discussion_offset ?? 0));
    if (context.discussion_kind) params.set("kind", context.discussion_kind);
    if (context.discussion_state) params.set("state", context.discussion_state);
    if (context.discussion_from) params.set("date_from", context.discussion_from);
    if (context.discussion_to) params.set("date_to", context.discussion_to);
    if (context.unknown_date) params.set("unknown_date", "true");
    return `/github-repositories/discussions?${params}`;
  }
  if (context.tab === "documents") {
    params.set("path", context.path!); params.set("offset", String(context.snapshot_offset));
    return `/github-repositories/document-snapshots?${params}`;
  }
  params.set("kind", context.tab === "commits" ? "commit" : "unclassified");
  params.set("offset", String(context.offset));
  return `/github-repositories/records?${params}`;
}
export function discussionTarget(scope: string, parentKind: "pull_request" | "issue", parentId: string,
  outer: EntryListContext, focus?: number) {
  return repositoryTarget({scope, tab:"discussions", offset:0, doc_offset:0, snapshot_offset:0, path:null, outer,
    thread_kind:parentKind, thread_id:parentId, focus_entry_id:focus});
}
export function eventDay(value: string | null) {
  return value ? new Intl.DateTimeFormat("en-US", {timeZone:"Asia/Seoul",dateStyle:"long"}).format(new Date(value)) : "Date unknown";
}

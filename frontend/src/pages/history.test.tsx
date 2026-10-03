import { beforeEach, afterEach, it, expect, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router";
import EntryDetailPage from "./EntryDetailPage";
import SourcesPage from "./SourcesPage";
import type { Entry } from "../api/entries";

const initial: Entry = { id: 7, source: "codex", provider: "codex", external_id: "session-1", source_scope: "default",
  title: "Imported session", type: "CONVERSATION", content: "Current source text", current_version_id: 20,
  read_only: true, source_state: "available", external_ai_allowed: false, review_required: true,
  event_at: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" };
let record: Entry;
let denied: boolean;
let calls: { path: string; method: string; body?: unknown }[];
function mount(path: string) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/entries/:id" element={<EntryDetailPage />} /><Route path="/sources" element={<SourcesPage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  localStorage.setItem("access_token", "test"); record = { ...initial }; calls = []; denied = true;
  vi.stubGlobal("confirm", vi.fn(() => true));
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit = {}) => {
    const method = options.method ?? "GET";
    const body = options.body ? JSON.parse(options.body as string) : undefined;
    calls.push({ path, method, body });
    if (path === "/api/entries/7") return Response.json(record);
    if (path === "/api/entries/7/settings") { record = { ...record, ...body }; return Response.json(record); }
    if (path === "/api/entries/7/source-state") { record.source_state = body.state; return Response.json(record); }
    if (path === "/api/entries/7/versions") return Response.json([
      { id: 20, number: 2, title: "Current", content: "Current source text", completeness: "complete", parser_version: "demo-v1", material_kind: "sanitized_capture", observed_at: "2026-01-02T00:00:00Z", source_updated_at: null },
      { id: 19, number: 1, title: "Partial version", content: "Older text", completeness: "partial", parser_version: "demo-v1", material_kind: "sanitized_capture", observed_at: "2026-01-01T00:00:00Z", source_updated_at: null },
    ]);
    if (path === "/api/entries/7/versions/19/select") { record.current_version_id = 19; record.content = "Older text"; record.review_required = false; return Response.json(record); }
    if (path === "/api/sources") return Response.json([{ id: 1, provider: "codex", scope: "default", collection_enabled: true, external_ai_allowed: false }]);
    if (path.startsWith("/api/collection-runs?")) return Response.json([{ id: 2, scope: "mac:synthetic", status: "partial", started_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T01:00:00Z", completed_at: "2026-01-01T01:00:00Z", expected_items: 3, counts: { new: 2, blocked: 1 }, coverage: { discovered: 4, selected: 3, excluded: 1, read: 2, failed: 0, deferred: 1, gaps: ["ACTIVE_SESSION"] } }]);
    if (path === "/api/sources/suppressed/records") return Response.json(denied ? [{ id: 3, provider: "codex", external_id: "deleted-1", deleted_at: "2026-01-01T00:00:00Z" }] : []);
    if (path === "/api/sources/purges/status") return Response.json({ pending: 1, failed_attempts: 2, errors: [] });
    if (path === "/api/sources/1") return Response.json({ id: 1, provider: "codex", scope: "default", ...body });
    if (path === "/api/sources/suppressed/3/allow-reimport") { denied = false; return new Response(null, { status: 204 }); }
    return new Response(null, { status: 404 });
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

it("shows imported read-only content and stores annotation separately", async () => {
  mount("/entries/7");
  await screen.findByText("Imported session");
  expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
  expect(screen.getByText(/snapshot needs review/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Personal annotation"), { target: { value: "My note" } });
  fireEvent.click(screen.getByText("Save annotation"));
  await waitFor(() => expect(record.annotation).toBe("My note"));
  expect(record.content).toBe("Current source text");
  expect(calls.find(c => c.path.endsWith("/settings"))?.body).toEqual({ annotation: "My note" });
});

it("keeps provenance lazy and confirms explicit selection of partial history", async () => {
  mount("/entries/7"); await screen.findByText("Imported session");
  expect(calls.some(c => c.path.endsWith("/versions"))).toBe(false);
  fireEvent.click(screen.getByText("View history and provenance"));
  await screen.findByText("Version 2 — Current");
  fireEvent.click(screen.getByText("Inspect version 1"));
  expect(screen.getByText("Older text")).toBeTruthy();
  fireEvent.click(screen.getByText("Use as current"));
  await waitFor(() => expect(record.current_version_id).toBe(19));
  expect(window.confirm).toHaveBeenCalled();
});

it("requires confirmation to mark a source deletion", async () => {
  mount("/entries/7"); await screen.findByText("Imported session");
  fireEvent.click(screen.getByText("Mark confirmed source deletion"));
  await waitFor(() => expect(record.source_state).toBe("deleted"));
  expect(calls.find(c => c.path.endsWith("/source-state"))?.body).toEqual({ state: "deleted", confirmed: true });
});

it("shows independent source controls, pending purge, and owner reimport action", async () => {
  mount("/sources"); await screen.findByText("codex · default");
  expect((screen.getByLabelText("Allow collection") as HTMLInputElement).checked).toBe(true);
  expect((screen.getByLabelText("Allow external AI for this source") as HTMLInputElement).checked).toBe(false);
  await screen.findByText("Pending objects: 1. Failed attempts: 2.");
  fireEvent.click(screen.getByText("Allow reimport"));
  await screen.findByText("No blocked records.");
  expect(window.confirm).toHaveBeenCalled();
});

it("shows Codex backfill coverage separately from collector freshness", async () => {
  mount("/sources");
  await screen.findByText("Backfill #2 · Partially completed");
  expect(screen.getByText(/4 discovered · 3 selected · 1 excluded/)).toBeTruthy();
  expect(screen.getByText(/2 new · 0 unchanged/)).toBeTruthy();
  expect(screen.getByText(/Collection is manual/)).toBeTruthy();
  expect(screen.getByText("active session")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Previous backfills" }).hasAttribute("disabled")).toBe(true);
});

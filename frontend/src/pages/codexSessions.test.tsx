import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../App";
import EntryListPage from "./EntryListPage";
import EntrySearchPage from "./EntrySearchPage";
import CodexSessionPage from "./CodexSessionPage";
import { safeSessionReturn } from "../utils/codexSessions";

const summary = { source_scope: "mac:demo", thread_id: "thread", title: "Session question", turn_count: 25,
  title_inferred: false, start_at: null, end_at: null, partial: false, review_required: false,
  order_unknown: false, archived: false, forked_from_id: null, metadata_conflict: false };
const record = { id: 21, title: "Turn 21", content: "user: Question\n\nassistant: interim zebra\n\nassistant: Final conclusion",
  current_version_id: 120, source: "codex", provider: "codex", type: "PROJECT_EVENT", source_scope: "mac:demo", read_only: true,
  annotation: null, source_state: "available", external_ai_allowed: false, event_at: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
let requests: string[]; let deleted: boolean;
beforeEach(() => {
  localStorage.setItem("access_token", "test-token"); requests = []; deleted = false;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input); requests.push(path);
    const url = new URL(path, "http://localhost");
    if (url.pathname === "/api/archive") return Response.json({ items: [{ kind: "codex_session", session: summary }], total: 1, limit: 20, offset: 0 });
    if (url.pathname === "/api/entries/search") {
      const matches = url.searchParams.get("include_work_commentary") === "true";
      return Response.json({ items: matches ? [{ ...record, preview_text: "interim zebra", session_ref: summary, matched_in_commentary_only: true }] : [], total: matches ? 1 : 0, limit: 20, offset: 0 });
    }
    if (url.pathname === "/api/codex-sessions/turns") {
      const focus = Number(url.searchParams.get("focus_entry_id"));
      return Response.json({ session: summary, total: deleted ? 24 : 25, limit: 20, offset: focus ? 20 : 0, focus_missing: deleted,
        items: deleted ? [{ id: 22, title: "Turn 22", current_version_id: 120, event_at: null, preview_text: "Final conclusion" }] : [{ id: focus || 1, title: `Turn ${focus || 1}`, current_version_id: 120, event_at: null, preview_text: "Final conclusion" }] });
    }
    const match = url.pathname.match(/^\/api\/entries\/(\d+)(\/presentation)?$/);
    if (match) {
      if (options.method === "DELETE") { deleted = true; return new Response(null, { status: 204 }); }
      return Response.json(match[2] ? { entry_id: Number(match[1]), version_id: 120, primary_content: "user: Question\n\nassistant: Final conclusion", payload: null, unknown_phase: false, has_final_answer: true } : { ...record, id: Number(match[1]), title: `Turn ${match[1]}` });
    }
    return Response.json([]);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });
function mount(path: string) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[path]}><Routes><Route element={<App />}>
    <Route path="/entries" element={<EntryListPage />} /><Route path="/search" element={<EntrySearchPage />} /><Route path="/sessions/codex" element={<CodexSessionPage />} />
  </Route></Routes></MemoryRouter></QueryClientProvider>);
  return cache;
}
describe("Codex session browsing", () => {
  it("opens a grouped session and separates commentary from primary reading", async () => {
    mount("/entries");
    fireEvent.click(await screen.findByRole("link", { name: "Session question" }));
    await screen.findByText("25 retained turns · Page 1");
    await screen.findByText("user: Question assistant: Final conclusion");
    const work = screen.getByText("Work details · commentary and recorded evidence").closest("details")!;
    expect(work.open).toBe(false);
    fireEvent.click(work.querySelector("summary")!);
    expect(work.open).toBe(true);
    expect(work.textContent).toContain("interim zebra");
    fireEvent.click(screen.getByRole("link", { name: "← Back to entries" }));
    await screen.findByRole("link", { name: "Session question" });
  });
  it("searches work commentary only when opted in and focuses its turn", async () => {
    mount("/search?q=zebra");
    await screen.findByText("No entries match your search.");
    fireEvent.click(screen.getByLabelText("Include work commentary from Codex"));
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    fireEvent.click(await screen.findByRole("link", { name: "Turn 21" }));
    await screen.findByText("25 retained turns · Page 2");
    await screen.findByText("user: Question assistant: Final conclusion");
    expect(requests.some(path => path.includes("focus_entry_id=21"))).toBe(true);
    expect(screen.getByRole("link", { name: "← Back to search" }).getAttribute("href")).toContain("include_work_commentary=true");
    fireEvent.click(screen.getByRole("button", { name: "Delete turn" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await screen.findByText("24 retained turns · Page 2");
    await screen.findByRole("button", { name: /Turn 22/ });
  });
  it("does not search for the work option alone and rejects unsafe return paths", async () => {
    mount("/search?include_work_commentary=true");
    await screen.findByText("What would you like to find?");
    await waitFor(() => expect(requests).toEqual([]));
    expect(safeSessionReturn("https://evil.example/sessions/codex?scope=a&thread=b")).toBeNull();
    expect(safeSessionReturn("/sessions/codex?scope=a&thread=b&returnTo=https://evil.example")).toContain("returnTo=%2Fentries");
  });
});

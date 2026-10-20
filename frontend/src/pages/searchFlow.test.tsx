import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import App from "../App";
import EntrySearchPage from "./EntrySearchPage";
import PassagePage from "./PassagePage";
import ConversationPage from "./ConversationPage";
import { setAccessToken } from "../utils/session";
const p = { id: 3, entry_id: 7, version_id: 9, field: "content", start: 0, end: 26, passage_hash: "a".repeat(64),
  title: "Saved worker location", text: "The worker runs on a host.", source: "manual", created_at: "2026-01-01T00:00:00Z", event_at: null,
  source_state: "unknown", completeness: "complete", index_status: "ready", gap_codes: [], work_only: false,
  projection_version: "v1", snapshot_count: 1, aliases: [], alias_total: 1 };
const consent = "Allow this question and selected originals to be sent to OpenAI and save this conversation";
const conversationId = "b".repeat(32), turnId = "c".repeat(32);
let conversation: Record<string, unknown>;
let enabled: boolean, revision: number, total: number, denied: boolean;
let gate: Promise<void> | undefined;
let sent: { url: string; options: RequestInit }[];
beforeEach(() => {
  localStorage.clear(); localStorage.setItem("access_token", "account-one");
  enabled = true; revision = 1; total = 1; denied = false; gate = undefined; sent = [];
  conversation = { id: conversationId, title: "Saved worker conversation", state: "active", revision: 0, filters: {}, updated_at: p.created_at, turns: [], unfinished: null, next_before: null };
  vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
    sent.push({ url, options });
    const coverage = { state: enabled ? "available" : "disabled", policy_revision: revision,
      matched_records: 2, allowed_records: 1, indexed_records: 1, ready_slices: 1, jobs: {} };
    if (url.startsWith("/api/answer-conversations")) {
      if (url.endsWith("/turns")) {
        const input = JSON.parse(options.body as string);
        const turn = { id: turnId, request_id: input.request_id, seq: 1, epoch: 0, q: input.q, base_turn_id: null, state: "created", branch: null,
          outcome: null, answer: null, answer_status: null, error_code: null, availability: "available", citations: [], usage: [], context_summary: {}, action_expires_at: p.created_at, lease_expires_at: null };
        conversation = { ...conversation, revision: 1, turns: [turn], unfinished: turn };
      }
      const stage = url.split("/").at(-1);
      if (["plan", "search", "answer", "stop"].includes(stage ?? "")) {
        if (stage === "search") await gate;
        const state = stage === "plan" ? "planned" : stage === "search" ? "ready" : stage === "answer" ? "completed" : "stopped";
        const turn = { ...(conversation.turns as object[])[0], state, branch: "search", outcome: stage === "answer" ? "answer" : null,
          answer: stage === "answer" ? p.text : null, answer_status: stage === "answer" ? "supported" : null,
          citations: stage === "answer" ? [{ entry_id: p.entry_id, version_id: p.version_id, field: p.field, start: p.start, end: p.end, passage_hash: p.passage_hash }] : [] };
        conversation = { ...conversation, turns: [turn], unfinished: stage === "answer" || stage === "stop" ? null : turn };
      }
      return Response.json(conversation);
    }
    if (url.includes("/semantic/status?")) return Response.json(coverage);
    if (url.endsWith("/answers/status")) return Response.json({ enabled, policy_revision: revision });
    if (url.endsWith("/semantic/search")) { await gate; return Response.json({ items: [{ embedding_id: 11, distance: 0.1, passage: p }], coverage }); }
    if (url.includes("/answers/recommendations?")) return Response.json({ passages: [p], omissions: [], policy_revision: revision, request_bytes: 1000 });
    if (url.endsWith("/answers")) return Response.json({ status: "supported", answer: "The worker runs on a host.", citations: [{ kind: "passage", source_id: 3, passage: p }], policy_revision: revision });
    if (url.includes("/passages/citation?")) return Response.json({ ...p, freshness: "current", current_version_id: 9, observed_at: p.created_at });
    if (url.includes("/passages/search?")) return denied ? new Response(null, { status: 404 }) : Response.json({ items: [p], total, limit: 20,
      offset: Number(new URL(url, "http://localhost").searchParams.get("offset") ?? 0), coverage: { ready: 1 } });
    if (url.includes("/entries/search?")) return denied ? new Response(null, { status: 404 }) : Response.json({ items: [{ id: 7, type: "NOTE", title: p.title, content: p.text, source: "manual", created_at: p.created_at, event_at: null }], total: 1, limit: 20, offset: 0 });
    throw new Error(`Unexpected request ${url}`);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount(path = "/search") {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[path]}><Routes><Route element={<App />}>
    <Route path="/citations" element={<PassagePage />} /><Route path="/search" element={<EntrySearchPage />} /><Route path="/passages/:id" element={<PassagePage />} />
    <Route path="/conversations/:id" element={<ConversationPage />} />
    <Route path="/login" element={<p>Login page</p>} />
  </Route></Routes></MemoryRouter></QueryClientProvider>);
  return cache;
}
const posts = () => sent.filter(x => x.options.method === "POST");
async function search() {
  fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "worker" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByRole("heading", { name: p.title });
}
async function ask() {
  fireEvent.click(screen.getByRole("button", { name: "Get an answer with sources" }));
  await waitFor(() => expect((screen.getByRole("checkbox", { name: consent }) as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("checkbox", { name: consent }));
  fireEvent.click(screen.getByRole("button", { name: "Ask from my records" }));
}
it("offers two user purposes and searches locally without an algorithm selector or provider checks", async () => {
  mount();
  expect(screen.queryByLabelText("Search mode")).toBeNull();
  expect(screen.getByRole("button", { name: "Search & ask" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByRole("button", { name: "Review a period" })).toBeTruthy();
  expect(sent).toHaveLength(0); await search();
  expect(sent).toHaveLength(1); expect(sent[0].url).toContain("/passages/search?");
  expect(sent[0].url).not.toContain("mode=");
  expect(screen.queryByText("Use this passage for an answer")).toBeNull();
  expect(screen.queryByText("Generate cited answer")).toBeNull();
  expect(posts()).toHaveLength(0);
});
it("keeps local results usable when AI is disabled", async () => {
  enabled = false; mount(); await search();
  fireEvent.click(screen.getByRole("button", { name: "Get an answer with sources" }));
  await screen.findByText(/AI answers are unavailable/);
  expect(screen.getByRole("heading", { name: p.title })).toBeTruthy();
  expect((screen.getByRole("button", { name: "Ask from my records" }) as HTMLButtonElement).disabled).toBe(true);
  expect(posts()).toHaveLength(0);
});
it("requires one consent for an integrated answer and hides internal evidence selection", async () => {
  mount(); await search();
  fireEvent.click(screen.getByRole("button", { name: "Get an answer with sources" }));
  await screen.findByRole("button", { name: "Ask from my records" });
  expect(posts()).toHaveLength(0);
  expect(screen.queryByRole("button", { name: "Choose evidence manually (advanced)" })).toBeNull();
  expect((screen.getByRole("button", { name: "Ask from my records" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox", { name: consent }));
  fireEvent.click(screen.getByRole("button", { name: "Ask from my records" }));
  await screen.findByRole("heading", { name: "Saved worker conversation" }); expect(posts()).toHaveLength(5);
});
it("keeps exact phrase matching local and strips UI-only query parameters", async () => {
  mount(); fireEvent.click(screen.getByLabelText("Match exact phrase")); await search();
  expect(sent).toHaveLength(1); expect(sent[0].url).toContain("/entries/search?");
  expect(sent[0].url).not.toMatch(/mode=|exact=/);
  expect(screen.queryByRole("button", { name: "Get an answer with sources" })).toBeNull();
  expect(screen.getByText(/Exact phrase search is local/)).toBeTruthy();
});
it("returns from a stable citation to the saved conversation without replay", async () => {
  total = 41; mount("/search?mode=search&q=worker&source=manual&offset=20");
  await screen.findByRole("heading", { name: p.title }); await ask();
  await screen.findByRole("heading", { name: "Saved worker conversation" });
  fireEvent.click(screen.getByRole("link", { name: /Original · Version 9/ }));
  await screen.findByText(/matches the current retained version/);
  fireEvent.click(screen.getByRole("link", { name: "Back to conversation" }));
  await screen.findByRole("heading", { name: "Saved worker conversation" });
  expect(posts()).toHaveLength(5);
});
it.each(["draft", "purpose", "version", "close", "account"])("stops later paid stages after %s changes", async change => {
  let finish!: () => void; gate = new Promise(resolve => { finish = resolve; });
  mount(); await search(); await ask(); await waitFor(() => expect(posts().some(p => p.url.endsWith("/search"))).toBe(true));
  if (change === "draft") fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "new question" } });
  if (change === "purpose") fireEvent.click(screen.getByRole("button", { name: "Review a period" }));
  if (change === "version") fireEvent.change(screen.getByLabelText("Record version"), { target: { value: "observed" } });
  if (change === "close") fireEvent.click(screen.getByRole("button", { name: "Close answer request" }));
  if (change === "account") act(() => setAccessToken("account-two"));
  await waitFor(() => expect(posts()[0].options.signal?.aborted).toBe(true)); finish();
  await waitFor(() => expect(posts().filter(p => p.url.endsWith("/answer"))).toHaveLength(0));
  expect(screen.queryByRole("heading", { name: "Saved worker conversation" })).toBeNull();
});
it("does not display another account's cached local results", async () => {
  mount("/search?mode=search&q=worker"); await screen.findByRole("heading", { name: p.title });
  denied = true; act(() => setAccessToken("account-two"));
  await screen.findByRole("alert"); expect(screen.queryByRole("heading", { name: p.title })).toBeNull();
  expect(posts()).toHaveLength(0);
});
it("hides cached local results when a refresh fails", async () => {
  const cache = mount("/search?mode=search&q=worker"); await screen.findByRole("heading", { name: p.title });
  denied = true; await act(async () => { await cache.invalidateQueries({ queryKey: ["passages"] }); });
  await screen.findByRole("alert"); expect(screen.queryByRole("heading", { name: p.title })).toBeNull();
});

it("keeps advanced options open when turning exact phrase matching off", async () => {
  mount("/search?mode=search&q=worker&exact=true"); await screen.findByRole("heading", { name: p.title });
  const panel = screen.getByText("Advanced options").closest("details")!;
  expect(panel.open).toBe(true);
  fireEvent.click(screen.getByLabelText("Match exact phrase"));
  expect(panel.open).toBe(true);
  expect((screen.getByLabelText("Record version") as HTMLSelectElement).disabled).toBe(false);
});

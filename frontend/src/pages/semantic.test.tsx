import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import App from "../App";
import EntrySearchPage from "./EntrySearchPage";
import PassagePage from "./PassagePage";

const passage = { id: 3, entry_id: 2, version_id: 4, field: "content", start: 100, end: 120, passage_hash: "a".repeat(64),
  title: "Synthetic worker", text: "Runs on the server.", source: "manual", created_at: "2026-01-01", event_at: null,
  source_state: "unknown", completeness: "complete", index_status: "ready", gap_codes: [], work_only: false,
  projection_version: "v1", snapshot_count: 1, alias_total: 2, aliases: [] };
let state: string;
let failure: number;
let revision: number;
let statusFailure: number;
let readerFailure: number;
let answerEnabled: boolean;
let sent: { url: string; options: RequestInit }[];
beforeEach(() => {
  localStorage.clear(); localStorage.setItem("access_token", "test-token");
  state = "available"; failure = 0; revision = 1; statusFailure = 0; readerFailure = 0; answerEnabled = false; sent = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit) => {
    sent.push({ url, options });
    const coverage = { state, policy_revision: revision, matched_records: 3, allowed_records: 2, indexed_records: 1, ready_slices: 1, jobs: {} };
    if (url.endsWith("/answers/status")) return Response.json({ enabled: answerEnabled, policy_revision: revision, selected_limit: 5, max_input_characters: 3000, output_limit_tokens: 512 });
    if (url.endsWith("/answers")) return Response.json({ status: "supported", answer: "Synthetic grounded draft.",
      citations: [{ embedding_id: 10, passage }], policy_revision: revision });
    if (url.includes("/status?")) return statusFailure ? new Response(null, { status: statusFailure }) : Response.json(coverage);
    if (url.endsWith("/search")) return failure ? Response.json({ detail: "PROVIDER_TIMEOUT_OR_NETWORK" }, { status: failure }) : Response.json({ items: [{ embedding_id: 10, distance: 0.1, passage }], coverage, truncated: false, limit: 20 });
    if (url.includes("/locations?")) return Response.json({ items: [{ embedding_id: 11, entry_id: 5, version_id: 8, start: 100, end: 120, event_at: null }], total: 1, limit: 20, offset: 0 });
    return readerFailure ? new Response(null, { status: readerFailure }) : Response.json(passage);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}>
    <MemoryRouter initialEntries={["/search?mode=semantic&q=where+is+the+worker&source=manual"]}><Routes><Route element={<App />}>
      <Route path="/search" element={<EntrySearchPage />} /><Route path="/semantic/slices/:id" element={<PassagePage semantic />} />
      <Route path="/login" element={<p>Login page</p>} />
    </Route></Routes></MemoryRouter>
  </QueryClientProvider>);
  return cache;
}
function paid() { return sent.filter(r => r.options.method === "POST"); }
async function submit() {
  await screen.findByText("Stored slices are available for semantic search.");
  fireEvent.click(screen.getByRole("checkbox", { name: "Send this question to OpenAI for this search" }));
  fireEvent.click(screen.getByRole("button", { name: "Search with OpenAI" }));
}
it("loads only local coverage and requires explicit consent before one POST", async () => {
  mount(); await screen.findByText("Stored slices are available for semantic search.");
  expect(paid()).toHaveLength(0);
  expect(sent[0].url).not.toContain("q=");
  expect((screen.getByRole("button", { name: "Search with OpenAI" }) as HTMLButtonElement).disabled).toBe(true);
  await submit(); await screen.findByText("Synthetic worker");
  expect(paid()).toHaveLength(1);
  const body = JSON.parse(paid()[0].options.body as string);
  expect(body.confirm_external_ai).toBe(true); expect(body.source).toBe("manual");
  expect(body.request_id).toMatch(/^[a-f0-9]{32}$/);
  expect(body.q).toBe("where is the worker");
  expect((screen.getByRole("checkbox", { name: "Send this question to OpenAI for this search" }) as HTMLInputElement).checked).toBe(false);
});
it("reviews a selected passage before a separate answer POST", async () => {
  answerEnabled = true; mount(); await submit(); await screen.findByText("Synthetic worker");
  await screen.findByText("0 of 5 passages selected");
  expect(paid()).toHaveLength(1);
  fireEvent.click(screen.getByRole("checkbox", { name: "Use this passage for an answer" }));
  await screen.findByText("1 of 5 passages selected");
  expect((screen.getByRole("button", { name: "Generate cited answer" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox", { name: "Send this question and the selected passages to OpenAI for an answer" }));
  fireEvent.click(screen.getByRole("button", { name: "Generate cited answer" }));
  await screen.findByText("Synthetic grounded draft.");
  expect(paid()).toHaveLength(2);
  const body = JSON.parse(paid()[1].options.body as string);
  expect(body.embedding_ids).toEqual([10]); expect(body.confirm_external_ai).toBe(true);
  expect(body.request_id).toMatch(/^[a-f0-9]{32}$/);
  expect((screen.getByRole("checkbox", { name: "Send this question and the selected passages to OpenAI for an answer" }) as HTMLInputElement).checked).toBe(false);
});
it("keeps the answer action disabled by default", async () => {
  mount(); await submit(); await screen.findByText("Synthetic worker");
  await screen.findByText("Answer generation is disabled on this server.");
  fireEvent.click(screen.getByRole("checkbox", { name: "Use this passage for an answer" }));
  expect((screen.getByRole("button", { name: "Generate cited answer" }) as HTMLButtonElement).disabled).toBe(true);
  expect(paid()).toHaveLength(1);
});
it.each(["unindexed", "indexing", "disabled", "unavailable"])("does not send when %s", async mode => {
  state = mode; mount();
  await waitFor(() => expect(sent).toHaveLength(1));
  fireEvent.click(screen.getByRole("checkbox", { name: "Send this question to OpenAI for this search" }));
  expect((screen.getByRole("button", { name: "Search with OpenAI" }) as HTMLButtonElement).disabled).toBe(true);
  expect(paid()).toHaveLength(0);
});
it("returns from an exact slice without repeating the paid search", async () => {
  mount(); await submit(); await screen.findByText("Synthetic worker");
  fireEvent.click(screen.getByRole("link", { name: "View passage" }));
  await screen.findByText(/Characters 101–120/);
  expect(screen.getByRole("link", { name: "Search" }).getAttribute("aria-current")).toBe("page");
  fireEvent.click(screen.getByRole("link", { name: "Back to search" }));
  await screen.findByText("Stored slices are available for semantic search.");
  expect((screen.getByLabelText("Search mode") as HTMLSelectElement).value).toBe("semantic");
  expect(screen.queryByText("Synthetic worker")).toBeNull();
  expect(paid()).toHaveLength(1);
});
it("loads retained locations without transmitting the question", async () => {
  mount(); await submit(); await screen.findByText("Synthetic worker");
  fireEvent.click(screen.getByRole("button", { name: "View 2 retained locations" }));
  await screen.findByText(/Record 5/);
  expect(sent.find(r => r.url.includes("/locations?"))!.url).not.toContain("q=");
  expect(paid()).toHaveLength(1);
});
it("shows timeout and does not retry or show an empty-success message", async () => {
  failure = 503; mount(); await submit();
  expect((await screen.findByRole("alert")).textContent).toContain("may have been charged");
  expect(screen.queryByText("No passages available")).toBeNull();
  expect(paid()).toHaveLength(1);
});
it("ends the session when the paid POST returns 401", async () => {
  failure = 401; mount(); await submit();
  await screen.findByText("Login page");
  expect(localStorage.getItem("access_token")).toBeNull();
  expect(paid()).toHaveLength(1);
});
it("hides old results after permissions change on local status refresh", async () => {
  mount(); await submit(); await screen.findByText("Synthetic worker");
  revision = 2; fireEvent.click(screen.getByRole("button", { name: "Refresh index status" }));
  await screen.findByText(/Records or permissions changed/);
  expect(screen.queryByText("Synthetic worker")).toBeNull();
  expect(paid()).toHaveLength(1);
});
it("hides cached results and blocks sending if the status refresh fails", async () => {
  mount(); await submit(); await screen.findByText("Synthetic worker");
  statusFailure = 503; fireEvent.click(screen.getByRole("button", { name: "Refresh index status" }));
  await screen.findByRole("alert");
  expect(screen.queryByText("Synthetic worker")).toBeNull();
  fireEvent.click(screen.getByRole("checkbox", { name: "Send this question to OpenAI for this search" }));
  expect((screen.getByRole("button", { name: "Search with OpenAI" }) as HTMLButtonElement).disabled).toBe(true);
});
it("hides cached source text when a semantic reader is no longer available", async () => {
  const cache = mount(); await submit(); await screen.findByText("Synthetic worker");
  fireEvent.click(screen.getByRole("link", { name: "View passage" }));
  await screen.findByText(/Characters 101–120/);
  readerFailure = 404;
  void cache.refetchQueries({ queryKey: ["semantic-slice"] });
  await screen.findByRole("alert");
  expect(screen.queryByText("Runs on the server.")).toBeNull();
});

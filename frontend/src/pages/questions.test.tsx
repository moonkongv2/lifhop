import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import App from "../App";
import EntrySearchPage from "./EntrySearchPage";
import PassagePage from "./PassagePage";
import { setAccessToken } from "../utils/session";

const passage = { id: 3, entry_id: 2, version_id: 4, field: "content", start: 0, end: 19,
  passage_hash: "a".repeat(64), title: "Synthetic worker", text: "Runs on the server.", source: "manual",
  created_at: "2026-01-01", event_at: null, source_state: "unknown", completeness: "complete",
  index_status: "ready", gap_codes: [], work_only: false, projection_version: "v1", snapshot_count: 1, alias_total: 1, aliases: [] };
const consentLabel = "Allow OpenAI to receive this question for search and answering, plus up to five automatically selected original passages";
let sent: { url: string; options: RequestInit }[];
let revision: number;
let enabled: boolean;
let indexed: boolean;
let empty: boolean;
let insufficient: boolean;
let failure: "search" | "proposal" | "answer" | undefined;
let changedProposal: boolean;
let gates: Partial<Record<"search" | "proposal" | "answer", Promise<void>>>;
beforeEach(() => {
  localStorage.clear(); localStorage.setItem("access_token", "test-token");
  sent = []; revision = 1; enabled = true; indexed = true; empty = false; insufficient = false;
  failure = undefined; changedProposal = false; gates = {};
  vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit) => {
    sent.push({ url, options });
    const current = revision;
    const coverage = { state: indexed ? "available" : "unindexed", policy_revision: current,
      matched_records: 3, allowed_records: 2, indexed_records: indexed ? 1 : 0, ready_slices: indexed ? 1 : 0, jobs: {} };
    if (url.endsWith("/answers/status")) return Response.json({ enabled, policy_revision: current, selected_limit: 5, max_input_characters: 10000, output_limit_tokens: 512 });
    if (url.includes("/semantic/status?")) return Response.json(coverage);
    if (url.endsWith("/semantic/search")) {
      await gates.search;
      return failure === "search" ? Response.json({ detail: "PROVIDER_TIMEOUT_OR_NETWORK" }, { status: 503 }) : Response.json({
        items: empty ? [] : [{ embedding_id: 10, distance: 0.1, passage }], coverage, limit: 20, truncated: false });
    }
    if (url.includes("/answers/recommendations?")) {
      await gates.proposal;
      return failure === "proposal" ? Response.json({}, { status: 409 }) : Response.json({
        passages: [passage], omissions: [], policy_revision: changedProposal ? current + 1 : current, request_bytes: 3000 });
    }
    if (url.endsWith("/answers")) {
      await gates.answer;
      return failure === "answer" ? Response.json({ detail: "EMBEDDING_BUDGET_EXHAUSTED" }, { status: 429 }) : Response.json({
        status: insufficient ? "insufficient" : "supported", answer: insufficient ? "The records do not say." : "The worker runs on the server.",
        citations: insufficient ? [] : [{ kind: "passage", source_id: 3, passage }], policy_revision: current });
    }
    return Response.json(passage);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
function mount() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={["/search?mode=answer&q=Where+does+the+worker+run%3F&source=manual"]}>
    <Routes><Route element={<App />}><Route path="/search" element={<EntrySearchPage />} />
      <Route path="/passages/:id" element={<PassagePage />} /><Route path="/login" element={<p>Login page</p>} />
    </Route></Routes></MemoryRouter></QueryClientProvider>);
  return cache;
}
function posts() { return sent.filter(r => r.options.method === "POST"); }
async function start() {
  await screen.findByRole("button", { name: "Ask from my records" });
  await waitFor(() => expect((screen.getByRole("checkbox", { name: consentLabel }) as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("checkbox", { name: consentLabel }));
  fireEvent.click(screen.getByRole("button", { name: "Ask from my records" }));
}

it("uses one consent/action for query, local recommendation and a bounded cited answer", async () => {
  mount(); await screen.findByRole("button", { name: "Ask from my records" });
  expect(posts()).toHaveLength(0);
  expect((screen.getByRole("button", { name: "Ask from my records" }) as HTMLButtonElement).disabled).toBe(true);
  await start(); await screen.findByText("The worker runs on the server.");
  expect(posts()).toHaveLength(3);
  const [search, local, answer] = posts().map(p => JSON.parse(p.options.body as string));
  expect(search.source).toBe("manual"); expect(search.confirm_external_ai).toBe(true);
  expect(local.embedding_ids).toEqual([10]); expect(local.policy_revision).toBe(1);
  expect(posts()[1].url).toContain("source=manual");
  expect(answer.passage_ids).toEqual([3]); expect(answer.embedding_ids).toBeUndefined();
  expect(answer.policy_revision).toBe(1); expect(answer.request_id).toBe(search.request_id);
  expect(answer.request_id).toMatch(/^[a-f0-9]{32}$/);
  expect((screen.getByRole("checkbox", { name: consentLabel }) as HTMLInputElement).checked).toBe(false);
  expect(screen.getByRole("link", { name: /Synthetic worker · Version 4/ }).getAttribute("href")).toContain("/passages/3?");
  fireEvent.click(screen.getByText("Review 1 passages used for this answer"));
  expect(screen.getByText("Runs on the server.")).toBeTruthy();
});

it("shows insufficient evidence without citations", async () => {
  insufficient = true; mount(); await start(); await screen.findByText("The records do not say.");
  expect(screen.getByText("Insufficient evidence")).toBeTruthy();
  expect(screen.queryByRole("link", { name: /Synthetic worker · Version 4/ })).toBeNull();
});
it("stops without an answer request when no evidence is found", async () => {
  empty = true; mount(); await start(); await screen.findByText(/No usable evidence was selected/);
  expect(posts()).toHaveLength(1);
});
it.each(["disabled", "unindexed"])("makes no paid request when %s", async state => {
  if (state === "disabled") enabled = false; else indexed = false;
  mount(); await screen.findByText(/AI answers are unavailable/);
  expect(posts()).toHaveLength(0);
  expect((screen.getByRole("button", { name: "Ask from my records" }) as HTMLButtonElement).disabled).toBe(true);
});
it.each(["search", "proposal", "answer"] as const)("does not retry after a %s failure", async step => {
  failure = step; mount(); await start();
  await screen.findByRole("alert");
  expect(posts()).toHaveLength(step === "search" ? 1 : step === "proposal" ? 2 : 3);
  expect((screen.getByRole("checkbox", { name: consentLabel }) as HTMLInputElement).checked).toBe(false);
});
it("blocks answer transmission if the recommendation revision changed", async () => {
  changedProposal = true; mount(); await start(); await screen.findByRole("alert");
  expect(posts()).toHaveLength(2);
});
it.each(["search", "proposal"] as const)("stopping during %s prevents later stages even if fetch resolves late", async step => {
  let finish!: () => void;
  gates[step] = new Promise(resolve => { finish = resolve; });
  mount(); await start();
  await screen.findByText(step === "search" ? "Finding related records..." : "Choosing original passages locally...");
  fireEvent.click(screen.getByRole("button", { name: "Stop" }));
  expect(posts().at(-1)!.options.signal?.aborted).toBe(true);
  finish(); await screen.findByText(/Stopped\. No later stage will run/);
  expect(posts()).toHaveLength(step === "search" ? 1 : 2);
});
it.each(["question", "filter", "account", "manual"])("drops pending work after a %s change", async change => {
  let finish!: () => void;
  gates.search = new Promise(resolve => { finish = resolve; });
  mount(); await start(); await screen.findByText("Finding related records...");
  if (change === "question") fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "Updated question" } });
  if (change === "filter") fireEvent.change(screen.getByLabelText("Source", { exact: true }), { target: { value: "github" } });
  if (change === "account") setAccessToken("other-account");
  if (change === "manual") fireEvent.click(screen.getByRole("button", { name: "Choose evidence manually (advanced)" }));
  await waitFor(() => expect(posts()[0].options.signal?.aborted).toBe(true));
  finish();
  expect(posts()).toHaveLength(1);
  expect(screen.queryByText("The worker runs on the server.")).toBeNull();
});
it("hides an old answer after a policy change and requires fresh consent", async () => {
  const cache = mount(); await start(); await screen.findByText("The worker runs on the server.");
  revision = 2;
  await cache.refetchQueries({ queryKey: ["answer-status"] });
  await cache.refetchQueries({ queryKey: ["semantic-status"] });
  await waitFor(() => expect(screen.queryByText("The worker runs on the server.")).toBeNull());
  expect((screen.getByRole("checkbox", { name: consentLabel }) as HTMLInputElement).checked).toBe(false);
});
it("returning from a citation preserves the answer mode without repeating any paid stage", async () => {
  mount(); await start(); await screen.findByText("The worker runs on the server.");
  fireEvent.click(screen.getByRole("link", { name: /Synthetic worker · Version 4/ }));
  await screen.findByText(/ORIGINAL PASSAGE/i);
  fireEvent.click(screen.getByRole("link", { name: "Back to search" }));
  await screen.findByRole("button", { name: "Ask from my records" });
  expect(screen.getByRole("button", { name: "Search & ask" }).getAttribute("aria-pressed")).toBe("true");
  expect(posts()).toHaveLength(3);
  expect(screen.queryByText("The worker runs on the server.")).toBeNull();
});

it("a double click starts only one query request", async () => {
  let finish!: () => void;
  gates.search = new Promise(resolve => { finish = resolve; });
  mount(); await start();
  fireEvent.click(screen.getByRole("button", { name: "Ask from my records" }));
  await screen.findByText("Finding related records...");
  expect(posts()).toHaveLength(1);
  finish(); await screen.findByText("The worker runs on the server.");
  expect(posts()).toHaveLength(3);
});

it("the whole-action deadline prevents later stages", async () => {
  let deadline!: () => void;
  const original = window.setTimeout.bind(window);
  vi.spyOn(window, "setTimeout").mockImplementation((handler, timeout, ...args) => {
    if (timeout === 60000 && typeof handler === "function") deadline = () => handler(...args);
    return original(handler, timeout, ...args);
  });
  let finish!: () => void;
  gates.search = new Promise(resolve => { finish = resolve; });
  mount(); await start(); await screen.findByText("Finding related records...");
  deadline(); finish();
  await screen.findByText(/The question timed out/);
  expect(posts()).toHaveLength(1);
});

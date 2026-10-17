import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import App from "../App";
import EntrySearchPage from "./EntrySearchPage";
import PassagePage from "./PassagePage";
import { setAccessToken } from "../utils/session";
const consentLabel = "Send this period summary request and the selected original passages with their dates to OpenAI";
const passage = { id: 3, entry_id: 2, version_id: 4, field: "content", start: 0, end: 22,
  passage_hash: "a".repeat(64), title: "Synthetic backup proposal", text: "Proposal: Add a backup.", source: "manual",
  created_at: "2026-10-17T00:00:00Z", event_at: "2026-01-15T00:00:00Z", source_state: "unknown",
  completeness: "complete", index_status: "ready", gap_codes: [], work_only: false, projection_version: "v1", snapshot_count: 1, alias_total: 1, aliases: [] };
let revision: number;
let enabled: boolean;
let empty: boolean;
let failure: boolean;
let insufficient: boolean;
let delayed: Promise<void> | undefined;
let sent: { url: string; options: RequestInit }[];
beforeEach(() => {
  localStorage.clear(); localStorage.setItem("access_token", "test-token");
  revision = 1; enabled = true; empty = false; failure = false; insufficient = false; delayed = undefined; sent = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit) => {
    sent.push({ url, options });
    const scope = { date_from: "2026-01-01", date_to: "2026-01-31", date_field: "event_at", source: null, type: null };
    const preview = { scope, policy_revision: revision, preview_digest: String(revision).repeat(64), matched_records: 30,
      allowed_records: 20, ready_records: 12, unique_records: 10, candidate_records: 10,
      selected_records: empty ? 0 : 1, byte_skipped: 2, missing_event_dates: 7, incomplete_selected: 0,
      passages: empty ? [] : [passage], partial: true, timezone: "Asia/Seoul" };
    if (url.includes("/retrospectives/preview?")) return Response.json(preview);
    if (url.endsWith("/answers/status")) return Response.json({ enabled, policy_revision: revision, selected_limit: 5, max_input_characters: 10000, output_limit_tokens: 512 });
    if (url.endsWith("/retrospectives")) {
      await delayed;
      return failure ? Response.json({ detail: "RETROSPECTIVE_PREVIEW_CHANGED" }, { status: 409 }) : Response.json({ preview,
        answer: { status: insufficient ? "insufficient" : "supported", answer: insufficient ? "No recorded activity is supported." : "[3] Proposal: Add a backup.",
          citations: insufficient ? [] : [{ kind: "passage", source_id: 3, passage }], policy_revision: revision } });
    }
    return Response.json(passage);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount(initial = "/search?mode=retrospective&date_from=2026-01-01&date_to=2026-01-31&date_field=event_at") {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[initial]}><Routes><Route element={<App />}>
    <Route path="/search" element={<EntrySearchPage />} /><Route path="/passages/:id" element={<PassagePage />} />
    <Route path="/login" element={<p>Login page</p>} />
  </Route></Routes></MemoryRouter></QueryClientProvider>);
  return cache;
}
const posts = () => sent.filter(x => x.options.method === "POST");
async function start() {
  await screen.findByRole("button", { name: "Summarize this period" });
  await waitFor(() => expect((screen.getByRole("checkbox", { name: consentLabel }) as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("checkbox", { name: consentLabel }));
  fireEvent.click(screen.getByRole("button", { name: "Summarize this period" }));
}
it("previews scope, coverage and original dates locally before one consented request", async () => {
  mount(); await screen.findByRole("button", { name: "Summarize this period" });
  expect(posts()).toHaveLength(0);
  expect(screen.getByText(/8 eligible records have no current body passage/)).toBeTruthy();
  expect(screen.getByText(/7 records for these source\/type filters have no source\/event date/)).toBeTruthy();
  expect(sent.find(x => x.url.includes("/retrospectives/preview?"))!.url).not.toContain("q=");
  await start(); await screen.findByText("Draft retrospective");
  expect(posts()).toHaveLength(1);
  const body = JSON.parse(posts()[0].options.body as string);
  expect(body.preview_digest).toBe("1".repeat(64)); expect(body.date_from).toBe("2026-01-01");
  expect(body.confirm_external_ai).toBe(true); expect(body.request_id).toMatch(/^[a-f0-9]{32}$/);
  expect(screen.getByRole("link", { name: "[3] Synthetic backup proposal" }).getAttribute("href")).toContain("/passages/3?");
  expect((screen.getByRole("checkbox", { name: consentLabel }) as HTMLInputElement).checked).toBe(false);
  expect(screen.getAllByText(/Proposal: Add a backup/)).toHaveLength(2);
  fireEvent.click(screen.getByText("Review 1 selected original passages"));
  expect(screen.getByText(/Source\/event: .*2026.*Added: .*2026/)).toBeTruthy();
});
it("shows insufficient evidence with no summary citation", async () => {
  insufficient = true; mount(); await start(); await screen.findByText("No recorded activity is supported.");
  expect(screen.getByText("Insufficient evidence")).toBeTruthy();
  expect(screen.queryByRole("link", { name: "[3] Synthetic backup proposal" })).toBeNull();
});
it.each(["empty", "disabled"])("does not send when %s", async value => {
  if (value === "empty") empty = true; else enabled = false;
  mount(); await screen.findByRole("button", { name: "Summarize this period" });
  expect((screen.getByRole("button", { name: "Summarize this period" }) as HTMLButtonElement).disabled).toBe(true);
  expect(posts()).toHaveLength(0);
});
it("shows a changed-preview error and never retries automatically", async () => {
  failure = true; mount(); await start(); await screen.findByRole("alert");
  expect(posts()).toHaveLength(1);
  expect((screen.getByRole("checkbox", { name: consentLabel }) as HTMLInputElement).checked).toBe(false);
});
it.each(["scope", "account", "stop"])("discards a delayed summary after %s change", async change => {
  let finish!: () => void;
  delayed = new Promise(resolve => { finish = resolve; });
  mount(); await start(); await screen.findByText("Summarizing selected records...");
  if (change === "scope") fireEvent.change(screen.getByLabelText("Date field"), { target: { value: "created_at" } });
  if (change === "account") setAccessToken("other-account");
  if (change === "stop") fireEvent.click(screen.getByRole("button", { name: "Stop" }));
  await waitFor(() => expect(posts()[0].options.signal?.aborted).toBe(true));
  finish();
  await waitFor(() => expect(screen.queryByText("Summarizing selected records...")).toBeNull());
  expect(screen.queryByText("Draft retrospective")).toBeNull();
  expect(posts()).toHaveLength(1);
});
it("hides a previous draft when permissions change", async () => {
  const cache = mount(); await start(); await screen.findByText("Draft retrospective");
  revision = 2;
  await cache.refetchQueries({ queryKey: ["answer-status"] });
  await cache.refetchQueries({ queryKey: ["period-preview"] });
  await waitFor(() => expect(screen.queryByText("Draft retrospective")).toBeNull());
  expect((screen.getByRole("checkbox", { name: consentLabel }) as HTMLInputElement).checked).toBe(false);
});
it("preserves retrospective scope on citation return without resending", async () => {
  mount(); await start(); await screen.findByText("Draft retrospective");
  fireEvent.click(screen.getByRole("link", { name: "[3] Synthetic backup proposal" }));
  await screen.findByText(/ORIGINAL PASSAGE/i);
  fireEvent.click(screen.getByRole("link", { name: "Back to search" }));
  await screen.findByRole("button", { name: "Summarize this period" });
  expect((screen.getByLabelText("Search mode") as HTMLSelectElement).value).toBe("retrospective");
  expect(posts()).toHaveLength(1);
});
it("requires dates and an ordered range within 92 days without requiring a question", async () => {
  mount("/search");
  fireEvent.change(screen.getByLabelText("Search mode"), { target: { value: "retrospective" } });
  expect(screen.queryByLabelText("Search query")).toBeNull();
  expect((screen.getByLabelText("Date field") as HTMLSelectElement).value).toBe("event_at");
  fireEvent.click(screen.getByRole("button", { name: "Review period" }));
  expect((await screen.findByRole("alert")).textContent).toContain("92 days");
  expect(posts()).toHaveLength(0);
});

it("choosing a new date in the calendar invalidates the reviewed consent and draft", async () => {
  mount(); await start(); await screen.findByText("Draft retrospective");
  fireEvent.click(screen.getByLabelText("Choose end date"));
  fireEvent.click(within(screen.getByRole("group", { name: "End date calendar" })).getByRole("button", { name: "2026-01-20" }));
  await screen.findByText("Review your updated question and filters before asking.");
  expect(screen.queryByText("Draft retrospective")).toBeNull();
  expect(posts()).toHaveLength(1);
});

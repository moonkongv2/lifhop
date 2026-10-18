import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import EntrySearchPage from "./EntrySearchPage";
import PassagePage from "./PassagePage";
import App from "../App";

const passage = { id: 11, entry_id: 7, version_id: 9, field: "content", start: 2, end: 32,
  passage_hash: "a".repeat(64), title: "Saved worker explanation", text: "Worker runs on the server. <script>unsafe</script>",
  source: "manual", created_at: "2026-01-01T00:00:00Z", event_at: null, source_state: "unknown",
  completeness: "complete", index_status: "ready", gap_codes: [], work_only: false,
  projection_version: "v1", snapshot_count: 1, aliases: [], alias_total: 1 };
let requests: string[];
let failure: number;
let total: number;
let aliases: number;
let answerEnabled: boolean;
let paid: RequestInit[];

beforeEach(() => {
  localStorage.clear(); localStorage.setItem("access_token", "test-token");
  requests = []; failure = 0; total = 1; aliases = 1; answerEnabled = false; paid = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit = {}) => {
    requests.push(path);
    if (path.endsWith("/answers/status")) return Response.json({ enabled: answerEnabled, policy_revision: 1, selected_limit: 5, max_input_characters: 10000, output_limit_tokens: 512 });
    if (path.endsWith("/answers")) { paid.push(options); return Response.json({ status: "supported", answer: "The worker runs on the server.",
      citations: [{ kind: "passage", source_id: 11, passage }], policy_revision: 1 }); }
    if (failure) return new Response(null, { status: failure });
    if (path.includes("/snapshots?")) return Response.json({ items: [{ ...passage, id: 12 }], total: 1, limit: 20, offset: 0 });
    if (path.includes("/search?")) {
      const offset = Number(new URL(path, "http://localhost").searchParams.get("offset") ?? 0);
      return Response.json({ items: [{ ...passage, alias_total: aliases }], total, limit: 20, offset,
        coverage: { ready: 2, pending: 1 }, timezone: "Asia/Seoul", search_version: "v1", projection_version: "v1", configuration_hash: "a" });
    }
    return Response.json(passage);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function mount(path = "/search?mode=passages&q=worker") {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}>
    <MemoryRouter initialEntries={[path]}><Routes><Route element={<App />}>
      <Route path="/search" element={<EntrySearchPage />} /><Route path="/passages/:id" element={<PassagePage />} />
      <Route path="/semantic/slices/:id" element={<PassagePage semantic />} />
      <Route path="/login" element={<p>Login page</p>} />
    </Route></Routes></MemoryRouter>
  </QueryClientProvider>);
  return cache;
}

it("keeps initial searches empty until a query or filter is submitted", () => {
  mount("/search");
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  expect(screen.queryByRole("alert")).toBeNull();
  expect(requests).toHaveLength(0);
});

it("opens a pinned passage and returns to its query, filters, mode and page", async () => {
  total = 41;
  mount("/search?mode=passages&q=worker&source=manual&offset=20");
  await screen.findByText("Saved worker explanation");
  expect(requests[0]).toContain("q=worker");
  expect(requests[0]).not.toContain("mode=");
  expect(screen.getByText(/Index coverage:/).textContent).toContain("1 pending");
  fireEvent.click(screen.getByText("View passage"));
  await screen.findByText(/Characters 3–32/);
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getByRole("link", { name: "Search" }).getAttribute("aria-current")).toBe("page");
  fireEvent.click(screen.getByText("Back to search"));
  await screen.findByText(/41 passages · Page 2/);
  expect(screen.getByRole("button", { name: "Search & ask" }).getAttribute("aria-pressed")).toBe("true");
  expect((screen.getByLabelText("Source") as HTMLSelectElement).value).toBe("manual");
});

it("loads snapshot locations only when expanded", async () => {
  aliases = 8;
  mount();
  await screen.findByText("Saved worker explanation");
  expect(requests.some(p => p.includes("snapshots"))).toBe(false);
  fireEvent.click(screen.getByText("View 8 retained locations"));
  await screen.findByText(/Record 7/);
  expect(requests.some(p => p.includes("/11/snapshots?") && p.includes("q=worker"))).toBe(true);
});

it("answers from a selected local passage with a separate consent", async () => {
  answerEnabled = true;
  mount();
  await screen.findByText("Saved worker explanation");
  await screen.findByText("0 of 5 passages selected");
  await waitFor(() => expect((screen.getByRole("checkbox", { name: "Send this question and the selected passages to OpenAI for an answer" }) as HTMLInputElement).disabled).toBe(false));
  expect(paid).toHaveLength(0);
  fireEvent.click(screen.getByRole("checkbox", { name: "Use this passage for an answer" }));
  expect((screen.getByRole("button", { name: "Generate cited answer" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox", { name: "Send this question and the selected passages to OpenAI for an answer" }));
  expect(screen.getByRole("region", { name: "Cited answer" }).textContent).toContain("1 of 5 passages selected");
  expect((screen.getByRole("checkbox", { name: "Send this question and the selected passages to OpenAI for an answer" }) as HTMLInputElement).checked).toBe(true);
  await waitFor(() => expect((screen.getByRole("button", { name: "Generate cited answer" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Generate cited answer" }));
  await waitFor(() => expect(paid).toHaveLength(1));
  expect(screen.getByRole("region", { name: "Cited answer" }).textContent).toContain("Draft answer");
  await screen.findByText("The worker runs on the server.");
  expect(paid).toHaveLength(1);
  const body = JSON.parse(paid[0].body as string);
  expect(body.passage_ids).toEqual([11]);
  expect(body.embedding_ids).toBeUndefined();
  expect(body.confirm_external_ai).toBe(true);
  expect(screen.getByRole("link", { name: /Saved worker explanation · Version 9/ }).getAttribute("href")).toContain("/passages/11?");
});

it.each([404, 503])("shows unavailable or timeout %s without presenting empty results", async status => {
  failure = status;
  mount(status === 404 ? "/passages/11?returnTo=%2Fsearch%3Fmode%3Dpassages%26q%3Dworker" : undefined);
  expect((await screen.findByRole("alert")).textContent).toContain(status === 404 ? "unavailable" : "within its limits");
  expect(screen.queryByText("No matching passages")).toBeNull();
  expect(requests).toHaveLength(1);
});

it("expires authentication on a 401", async () => {
  failure = 401;
  mount();
  await screen.findByText("Login page");
  await waitFor(() => expect(localStorage.getItem("access_token")).toBeNull());
});


const pinnedPath = "/passages/11?version_id=9&field=content&start=2&end=32&passage_hash=" + "a".repeat(64) + "&returnTo=%2Fsearch%3Fmode%3Dpassages%26q%3Dworker";

it.each(["current", "updated"])("reads the exact citation anchor and displays %s freshness", async freshness => {
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    requests.push(path);
    return Response.json({ ...passage, freshness, current_version_id: freshness === "current" ? 9 : 10,
      observed_at: "2026-01-01T00:00:00Z" });
  }));
  mount(pinnedPath);
  await screen.findByText(freshness === "current" ? /matches the current retained version/ : /Showing the cited version 9; current version: 10/);
  expect(requests[0]).toContain("/passages/citation?");
  expect(requests[0]).toContain("passage_hash=" + "a".repeat(64));
  expect(requests[0]).not.toContain("returnTo");
  expect(screen.getByText(passage.text).textContent).toBe(passage.text);
  expect(screen.getByRole("link", { name: "Open current record" }).getAttribute("href")).toContain("/entries/7?");
  expect(document.querySelector("script")).toBeNull();
});

it("hides previously loaded citation text when a deletion recheck fails", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => failure ? new Response(null, { status: failure }) : Response.json({
    ...passage, freshness: "updated", source_state: "deleted", current_version_id: 10, observed_at: passage.created_at,
  })));
  const cache = mount(pinnedPath);
  await screen.findByText("Deleted at source. This is a retained local version.");
  expect(screen.getByText(passage.text)).toBeTruthy();
  failure = 404;
  await act(async () => { await cache.invalidateQueries(); });
  expect((await screen.findByRole("alert")).textContent).toContain("unavailable");
  expect(screen.queryByText(passage.text)).toBeNull();
});


it("opens Semantic citations through the retained anchor without loading an embedding", async () => {
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    requests.push(path);
    return Response.json({ ...passage, freshness: "current", current_version_id: 9, observed_at: passage.created_at });
  }));
  mount(pinnedPath.replace("/passages/11", "/semantic/slices/11"));
  await screen.findByText(/matches the current retained version/);
  expect(requests).toHaveLength(1);
  expect(requests[0]).toContain("/passages/citation?");
});

it("rejects an incomplete citation anchor instead of falling back to a current passage", async () => {
  failure = 422;
  mount(pinnedPath.replace("version_id=9&", ""));
  await screen.findByRole("alert");
  expect(requests).toHaveLength(1);
  expect(requests[0]).toContain("/passages/citation?");
});

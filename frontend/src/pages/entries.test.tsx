import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import EntryListPage from "./EntryListPage";
import EntrySearchPage from "./EntrySearchPage";
import App from "../App";
import { entryTarget } from "../utils/entryNavigation";
import EntryCreatePage from "./EntryCreatePage";
import EntryDetailPage from "./EntryDetailPage";
import LoginPage from "./LoginPage";
import type { Entry } from "../api/entries";

const note: Entry = {
  id: 1, source: "manual", source_scope: "default", read_only: false, source_state: "unknown", external_ai_allowed: false, review_required: false, type: "NOTE", title: "여행 메모", content: "첫 줄\n둘째 줄",
  event_at: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
};
let records: Entry[];
let failedMethod: string | undefined;
let failureStatus: number;
let requests: { path: string; method: string }[];

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  localStorage.setItem("access_token", "test-token");
  records = [];
  requests = [];
  failedMethod = undefined;
  failureStatus = 500;
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit = {}) => {
    const method = options.method ?? "GET";
    requests.push({ path, method });
    expect((options.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
    if (method === failedMethod) return new Response(null, { status: failureStatus });
    if (method === "POST") {
      const body = JSON.parse(options.body as string);
      records = [{ ...note, ...body, title: body.title.trim() }];
      return Response.json(records[0], { status: 201 });
    }
    if (method === "PATCH") {
      records = [{ ...records[0], ...JSON.parse(options.body as string) }];
      return Response.json(records[0]);
    }
    if (method === "DELETE") {
      records = records.filter((entry) => entry.id !== Number(path.split("/").at(-1)));
      return new Response(null, { status: 204 });
    }
    if (path.startsWith("/api/archive?")) {
      const offset = Number(new URL(path, "http://localhost").searchParams.get("offset") ?? 0);
      return Response.json({ items: records.slice(offset, offset + 20).map(entry => ({ kind: "entry", entry })), total: records.length, limit: 20, offset });
    }
    if (path.startsWith("/api/entries/search?")) {
      const params = new URL(path, "http://localhost").searchParams;
      const offset = Number(params.get("offset") ?? 0);
      return Response.json({ items: records.slice(offset, offset + 20), total: records.length, limit: 20, offset, timezone: "Asia/Seoul" });
    }
    const record = records.find((entry) => entry.id === Number(path.split("/").at(-1)));
    return record ? Response.json(record) : new Response(null, { status: 404 });
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function mount(path = "/entries", queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })) {
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<App />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/search" element={<EntrySearchPage />} />
          <Route path="/entries" element={<EntryListPage />} />
          <Route path="/entries/new" element={<EntryCreatePage />} />
          <Route path="/entries/:id" element={<EntryDetailPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

function click(text: string) {
  if (text === "Delete") fireEvent.click(screen.getByLabelText("Record actions"));
  fireEvent.click(text === "Search" ? screen.getByRole("button", { name: text }) : screen.getByText(text));
}
function fill(title: string, content: string) {
  fireEvent.change(screen.getByLabelText("Title"), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("Content"), { target: { value: content } });
}

describe("Entry browser flow", () => {
  it("creates, lists, edits and deletes a note following server results", async () => {
    mount();
    await screen.findByText("No entries yet.");
    click("New note");
    fill(" 여행 메모 ", "첫 줄\n둘째 줄");
    click("Save");
    await screen.findByRole("heading", { name: "여행 메모" });
    click("← Back to entries");
    await screen.findByRole("heading", { name: "여행 메모" });
    click("여행 메모");
    click("Edit");
    expect((screen.getByLabelText("Content") as HTMLTextAreaElement).value).toBe("첫 줄\n둘째 줄");
    fill("수정한 메모", "");
    click("Save");
    await screen.findByRole("heading", { name: "수정한 메모" });
    click("← Back to entries");
    await screen.findByRole("heading", { name: "수정한 메모" });
    click("수정한 메모");
    click("Delete");
    click("Cancel");
    expect(requests.some((r) => r.method === "DELETE")).toBe(false);
    click("Delete");
    click("Confirm delete");
    await screen.findByText("No entries yet.");
  });

  it("rejects blank titles and preserves a draft when save fails", async () => {
    mount("/entries/new");
    fill("   ", "초안");
    click("Save");
    await screen.findByRole("alert");
    expect(requests).toHaveLength(0);
    fill("제목", "초안");
    failedMethod = "POST";
    click("Save");
    await screen.findByText(/Request failed: 500/);
    expect((screen.getByLabelText("Content") as HTMLTextAreaElement).value).toBe("초안");
    failedMethod = undefined;
    click("Save");
    await screen.findByRole("heading", { name: "제목" });
  });

  it("keeps the server record and form on edit failure, and supports cancellation", async () => {
    records = [note];
    mount("/entries/1");
    await screen.findByRole("heading", { name: note.title });
    click("Edit");
    fill("초안 수정", "내용 수정");
    failedMethod = "PATCH";
    failureStatus = 422;
    click("Save");
    await screen.findByText(/Please check your input/);
    expect(records[0].title).toBe(note.title);
    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe("초안 수정");
    click("Cancel");
    await screen.findByRole("heading", { name: note.title });
  });

  it("keeps the detail visible on delete failure and allows retry", async () => {
    records = [note];
    mount("/entries/1");
    await screen.findByRole("heading", { name: note.title });
    click("Delete");
    failedMethod = "DELETE";
    click("Confirm delete");
    await screen.findByText(/Request failed: 500/);
    expect(records).toHaveLength(1);
    failedMethod = undefined;
    click("Confirm delete");
    await screen.findByText("No entries yet.");
  });

  it("shows loading and a recoverable list error", async () => {
    failedMethod = "GET";
    mount();
    expect(screen.getByRole("status").textContent).toBe("Loading...");
    await screen.findByRole("alert");
    failedMethod = undefined;
    click("Retry");
    await screen.findByText("No entries yet.");
  });

  it("shows a missing or inaccessible record", async () => {
    mount("/entries/99");
    await screen.findByText(/Entry not found/);
  });

  it("redirects unauthenticated visitors without requesting entries", async () => {
    localStorage.clear();
    mount("/entries/new");
    await screen.findByRole("heading", { name: "Login" });
    expect(requests).toHaveLength(0);
  });

  it("clears the previous account's cached records after login", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["entries"], [note]);
    queryClient.setQueryData(["entries", "q=private"], { items: [note], total: 1 });
    queryClient.setQueryData(["entry", "1"], note);
    vi.stubGlobal("fetch", vi.fn(async (path: string) => {
      if (path === "/api/auth/login") return Response.json({ access_token: "new-account-token" });
      return Response.json({ items: [], total: 0, limit: 20, offset: 0, timezone: "Asia/Seoul" });
    }));
    mount("/login", queryClient);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password" } });
    click("Log in");
    await screen.findByText("No entries yet.");
    expect(queryClient.getQueryData(["entry", "1"])).toBeUndefined();
    expect(queryClient.getQueryData(["entries", "q=private"])).toBeUndefined();
    expect(localStorage.getItem("access_token")).toBe("new-account-token");
  });

  it("explains an expired session", async () => {
    failedMethod = "GET";
    failureStatus = 401;
    mount();
    await screen.findByText("Your session has expired. Please log in again.");
  });

  it("disables resubmission while saving", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    mount("/entries/new");
    fill("제목", "내용");
    click("Save");
    await waitFor(() => expect((screen.getByLabelText("Title") as HTMLInputElement).disabled || screen.getByLabelText("Title").closest("fieldset")?.disabled).toBe(true));
    expect(screen.getByText("Saving...")).toBeTruthy();
  });
});


describe("Entry search and pagination", () => {
  it("restores URL filters and preserves them through detail navigation", async () => {
    records = [note];
    mount("/search?q=여행&source=manual&type=NOTE&date_field=event_at&date_from=2026-10-01&date_to=2026-10-02");
    await screen.findByRole("heading", { name: note.title });
    expect((screen.getByLabelText("Search query") as HTMLInputElement).value).toBe("여행");
    expect((screen.getByLabelText("Source") as HTMLSelectElement).value).toBe("manual");
    expect((screen.getByLabelText("Date field") as HTMLSelectElement).value).toBe("event_at");
    const firstPath = requests[0].path;
    expect(new URL(firstPath, "http://localhost").searchParams.get("date_to")).toBe("2026-10-02");
    click(note.title);
    await screen.findByText(/Source\/event date: Unknown/);
    click("← Back to search");
    await screen.findByRole("heading", { name: note.title });
    expect((screen.getByLabelText("Search query") as HTMLInputElement).value).toBe("여행");
    expect(requests.at(-1)?.path).toBe(firstPath);
  });

  it("paginates without losing a query and resets the page on a new filter", async () => {
    records = Array.from({ length: 21 }, (_, i) => ({ ...note, id: i + 1, title: `메모 ${i + 1}` }));
    mount("/search?q=메모");
    await screen.findByText("21 entries · Page 1");
    expect((screen.getByText("Previous page") as HTMLButtonElement).disabled).toBe(true);
    click("Next page");
    await screen.findByText("21 entries · Page 2");
    expect(screen.queryByRole("heading", { name: "메모 1" })).toBeNull();
    expect((screen.getByText("Next page") as HTMLButtonElement).disabled).toBe(true);
    const params = new URL(requests.at(-1)!.path, "http://localhost").searchParams;
    expect(params.get("q")).toBe("메모");
    expect(params.get("offset")).toBe("20");
    fireEvent.change(screen.getByLabelText("Source"), { target: { value: "manual" } });
    click("Search");
    await screen.findByText("21 entries · Page 1");
    expect(new URL(requests.at(-1)!.path, "http://localhost").searchParams.get("source")).toBe("manual");
    expect(new URL(requests.at(-1)!.path, "http://localhost").searchParams.has("offset")).toBe(false);
    const requestCount = requests.length;
    click("Reset");
    await screen.findByRole("heading", { name: "What would you like to find?" });
    expect(requests).toHaveLength(requestCount);
  });

  it("validates calendar ranges before applying and shows filtered empty results", async () => {
    mount("/search?q=없는기록");
    await screen.findByText("No entries match your search.");
    const count = requests.length;
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-10-02" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-10-01" } });
    click("Search");
    await screen.findByText("Start date must be on or before end date.");
    expect(requests).toHaveLength(count);
  });

  it("moves back to the last existing page after deletion", async () => {
    records = Array.from({ length: 21 }, (_, i) => ({ ...note, id: i + 1, title: `기록 ${i + 1}` }));
    mount("/search?q=기록&offset=20");
    await screen.findByRole("heading", { name: "기록 21" });
    click("기록 21");
    await screen.findByText("Edit");
    click("Delete"); click("Confirm delete");
    await screen.findByText("20 entries · Page 1");
    await waitFor(() => expect(requests.at(-1)?.path).toBe("/api/entries/search?q=%EA%B8%B0%EB%A1%9D&limit=20"));
  });

  it("shows dates in Seoul even when the browser uses a different zone", async () => {
    records = [{ ...note, created_at: "2026-09-30T16:00:00Z" }];
    mount();
    await screen.findByText(/Added: Oct 1, 2026, 1:00 AM/);
  });
});

it("removes cached versions immediately after confirmed deletion", async () => {
  records = [{ ...note, read_only: true }];
  const cache = mount("/entries/1");
  cache.setQueryData(["entry-versions", 1], [{ content: "Retained synthetic text" }]);
  await screen.findByText(note.title);
  click("Delete");
  click("Confirm delete");
  await waitFor(() => expect(cache.getQueryData(["entry-versions", 1])).toBeUndefined());
  expect(records).toEqual([]);
});


describe("Panel record navigation", () => {
  it("keeps the selected search when switching records and clears the previous edit draft", async () => {
    const next = { ...note, id: 2, title: "Second note", content: "Second record content" };
    records = [note, next];
    mount("/search?q=notes&source=manual");
    await screen.findByRole("heading", { name: note.title });
    click(note.title);
    const sidebar = await screen.findByRole("complementary", { name: "Record navigation" });
    await waitFor(() => expect(within(sidebar).getByRole("link", { name: /Reading now/ }).getAttribute("aria-current")).toBe("page"));
    click("Edit");
    fill("Unsaved draft", "Do not carry this into another record");
    fireEvent.click(within(sidebar).getByRole("link", { name: /Second note/ }));
    await screen.findByRole("heading", { name: next.title });
    expect(screen.queryByLabelText("Title")).toBeNull();
    expect(screen.getByText(next.content)).toBeTruthy();
    expect(screen.getByRole("link", { name: "← Back to search" }).getAttribute("href")).toBe("/search?q=notes&source=manual");
    click("Edit");
    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe(next.title);
    expect(requests.some(request => request.method === "PATCH")).toBe(false);
  });

  it("closes the record menu for confirmation and cancels without deleting", async () => {
    records = [note];
    mount("/entries/1");
    await screen.findByRole("heading", { name: note.title });
    expect(screen.getByLabelText("Record actions").closest("details")?.open).toBe(false);
    click("Delete");
    expect(screen.getByRole("button", { name: "Confirm delete" })).toBeTruthy();
    expect(screen.getByLabelText("Record actions").closest("details")?.open).toBe(false);
    click("Cancel");
    expect(screen.queryByRole("button", { name: "Confirm delete" })).toBeNull();
    expect(requests.some(request => request.method === "DELETE")).toBe(false);
  });
});


describe("Dedicated Search page", () => {
  it("does not reuse recent Entries as results for an empty search sidebar", async () => {
    records = [note];
    const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    cache.setQueryData(["entries", ""], { items: [note], total: 1, limit: 20, offset: 0 });
    mount(entryTarget(1, { pathname: "/search", search: "" }), cache);
    await screen.findByRole("heading", { name: note.title });
    const sidebar = screen.getByRole("complementary", { name: "Record navigation" });
    expect(within(sidebar).getByText("Start a search to see matching records.")).toBeTruthy();
    expect(within(sidebar).getAllByRole("link")).toHaveLength(1);
    expect(requests.some(request => request.path.includes("/entries/search"))).toBe(false);
  });

  it("refreshes both Search and Entries after editing a record", async () => {
    records = [note];
    const cache = mount();
    await screen.findByRole("heading", { name: note.title });
    fireEvent.click(within(screen.getByRole("navigation", { name: "Main navigation" })).getByRole("link", { name: "Search" }));
    fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "여행" } });
    click("Search");
    await screen.findByRole("heading", { name: note.title });
    click(note.title);
    await screen.findByRole("button", { name: "Edit" });
    click("Edit");
    fill("Updated record", "Updated content"); click("Save");
    await screen.findByRole("heading", { name: "Updated record" });
    click("← Back to search");
    await screen.findByRole("heading", { name: "Updated record" });
    expect(cache.getQueryState(["archive", 0])?.isInvalidated).toBe(true);
    fireEvent.click(within(screen.getByRole("navigation", { name: "Main navigation" })).getByRole("link", { name: "Entries" }));
    await screen.findByRole("heading", { name: "Updated record" });
    await waitFor(() => expect(cache.getQueryState(["archive", 0])?.isInvalidated).toBe(false));
  });

  it("keeps a page-only Entries URL and corrects it after last-page deletion", async () => {
    records = Array.from({ length: 21 }, (_, i) => ({ ...note, id: i + 1, title: `Record ${i + 1}` }));
    mount("/entries?offset=20");
    await screen.findByRole("heading", { name: "Record 21" });
    expect(screen.queryByLabelText("Search query")).toBeNull();
    click("Record 21");
    expect((await screen.findByRole("link", { name: "← Back to entries" })).getAttribute("href")).toBe("/entries?offset=20");
    click("Delete"); click("Confirm delete");
    await screen.findByText("20 archive items · Page 1");
    expect(requests.at(-1)?.path).toBe("/api/archive?limit=20");
  });

  it.each(["/search", "/search?q=%20%20", "/search?date_field=event_at&offset=20"])("starts without an API request at %s", async path => {
    mount(path);
    await screen.findByRole("heading", { name: "What would you like to find?" });
    expect(requests).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "   " } });
    click("Search");
    expect(requests).toHaveLength(0);
  });

  it("queries only on submission and supports filters without a keyword", async () => {
    records = [note];
    mount("/search");
    fireEvent.change(screen.getByLabelText("Search query"), { target: { value: " 여행 " } });
    expect(requests).toHaveLength(0);
    fireEvent.submit(screen.getByLabelText("Search query").closest("form")!);
    await screen.findByRole("heading", { name: note.title });
    expect(new URL(requests[0].path, "http://localhost").searchParams.get("q")).toBe("여행");
    expect(screen.getByText("Title matches first")).toBeTruthy();
    click("Reset");
    fireEvent.change(screen.getByLabelText("Source"), { target: { value: "manual" } });
    click("Search");
    await screen.findByRole("heading", { name: note.title });
    const params = new URL(requests.at(-1)!.path, "http://localhost").searchParams;
    expect(params.get("source")).toBe("manual");
    expect(params.has("q")).toBe(false);
    expect(screen.getByText("Most recently added")).toBeTruthy();
  });

  it("redirects a legacy search URL before requesting its results", async () => {
    records = Array.from({ length: 21 }, (_, i) => ({ ...note, id: i + 1, title: `Record ${i + 1}` }));
    mount("/entries?q=travel&source=manual&offset=20&limit=50&junk=ignored");
    await screen.findByText("21 entries · Page 2");
    expect(requests).toHaveLength(1);
    expect(requests[0].path).toBe("/api/entries/search?q=travel&source=manual&offset=20&limit=20");
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getByRole("link", { name: "Search" }).getAttribute("aria-current")).toBe("page");
    expect(within(nav).getByRole("link", { name: "Entries" }).getAttribute("aria-current")).toBeNull();
  });

  it.each(["/entries?offset=-1", "/search?q=travel&offset=oops"])("blocks an invalid page then supports reset at %s", async path => {
    mount(path);
    await screen.findByText("Invalid page value. Please reset the page.");
    expect(requests).toHaveLength(0);
    click("Reset page");
    await screen.findByText(path.startsWith("/search") ? "No entries match your search." : "No entries yet.");
    expect(new URL(requests[0].path, "http://localhost").searchParams.has("offset")).toBe(false);
  });

  it.each(["/entries", "/search?q=travel"])("does not request unauthenticated data at %s", async path => {
    localStorage.clear();
    mount(path);
    await screen.findByRole("heading", { name: "Login" });
    expect(requests).toHaveLength(0);
  });

  it("preserves URL context and a single active navigation item on direct detail entry", async () => {
    records = [note];
    mount(entryTarget(1, { pathname: "/search", search: "q=travel&source=manual" }));
    await screen.findByRole("heading", { name: note.title });
    expect(screen.getByRole("link", { name: "← Back to search" }).getAttribute("href")).toBe("/search?q=travel&source=manual");
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    const selected = within(nav).getAllByRole("link").filter(link => link.getAttribute("aria-current") === "page");
    expect(selected).toHaveLength(1);
    expect(selected[0].textContent).toBe("Search");
    expect(selected[0].className).toBe("active");
  });

  it("returns a missing record to its search and safely falls back from an external destination", async () => {
    mount(entryTarget(99, { pathname: "/search", search: "q=travel" }));
    await screen.findByText(/Entry not found/);
    expect(screen.getByRole("link", { name: "Back to search" }).getAttribute("href")).toBe("/search?q=travel");
    cleanup();
    mount("/entries/99?returnTo=https%3A%2F%2Fevil.example");
    await screen.findByText(/Entry not found/);
    expect(screen.getByRole("link", { name: "Back to entries" }).getAttribute("href")).toBe("/entries");
  });

  it("keeps Entries pagination through creation cancellation and save", async () => {
    const path = entryTarget("new", { pathname: "/entries", search: "offset=20" });
    mount(path);
    click("Cancel");
    await screen.findByText("No entries yet.");
    expect(requests[0].path).toBe("/api/archive?limit=20&offset=20");
    cleanup();
    mount(path);
    fill("New record", "New content");
    click("Save");
    await screen.findByRole("heading", { name: "New record" });
    expect(screen.getByRole("link", { name: "← Back to entries" }).getAttribute("href")).toBe("/entries?offset=20");
  });

  it("keeps an empty search after deletion and removes its now-invalid offset", async () => {
    records = [note];
    mount(entryTarget(1, { pathname: "/search", search: "q=travel&offset=20" }));
    await screen.findByRole("heading", { name: note.title });
    click("Delete"); click("Confirm delete");
    await screen.findByText("0 entries · Page 1");
    expect((screen.getByLabelText("Search query") as HTMLInputElement).value).toBe("travel");
    expect(screen.getByText("No entries match your search.")).toBeTruthy();
    expect(requests.at(-1)?.path).toBe("/api/entries/search?q=travel&limit=20");
    click("Reset");
    await screen.findByRole("heading", { name: "What would you like to find?" });
  });

  it("retries a failed search while preserving its submitted filters", async () => {
    failedMethod = "GET";
    mount("/search?source=manual");
    await screen.findByText(/Request failed: 500/);
    failedMethod = undefined;
    click("Retry");
    await screen.findByText("No entries match your search.");
    expect(requests.at(-1)?.path).toBe("/api/entries/search?source=manual&limit=20");
  });
});


describe("English controls and account navigation", () => {
  it("shows Logout for a signed-in account and clears all cached private data", async () => {
    const cache = mount("/search");
    cache.setQueryData(["entry", "1"], note);
    cache.setQueryData(["entry-versions", 1], [{ content: "Synthetic private version" }]);
    cache.setQueryData(["sources"], [{ provider: "manual" }]);
    expect(screen.queryByRole("link", { name: "Login" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Logout" }));
    await screen.findByRole("heading", { name: "Login" });
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(cache.getQueryCache().getAll()).toHaveLength(0);
    expect(screen.getByRole("link", { name: "Login" })).toBeTruthy();
    expect(requests).toHaveLength(0);
  });

  it("reflects logout in another tab even on a Search screen with no query", async () => {
    const cache = mount("/search");
    cache.setQueryData(["entry", "1"], note);
    localStorage.removeItem("access_token");
    fireEvent(window, new StorageEvent("storage", { key: "access_token", newValue: null }));
    await screen.findByRole("heading", { name: "Login" });
    expect(cache.getQueryData(["entry", "1"])).toBeUndefined();
    expect(screen.queryByRole("button", { name: "Logout" })).toBeNull();
  });

  it("uses English validation for empty login fields", async () => {
    localStorage.clear();
    mount("/login");
    fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form")!);
    await screen.findByText("Enter a valid email address and password.");
    expect(requests).toHaveLength(0);
  });

  it("chooses dates through an English calendar and rejects impossible typed dates", async () => {
    mount("/search?date_from=2026-10-01");
    await screen.findByText("No entries match your search.");
    const input = screen.getByLabelText("Start date") as HTMLInputElement;
    expect(input.placeholder).toBe("YYYY-MM-DD");
    fireEvent.click(screen.getByLabelText("Choose start date"));
    const calendar = within(screen.getByRole("group", { name: "Start date calendar" }));
    expect(calendar.getByText("October 2026")).toBeTruthy();
    fireEvent.click(calendar.getByRole("button", { name: "2026-10-03" }));
    expect(input.value).toBe("2026-10-03");
    const count = requests.length;
    fireEvent.change(input, { target: { value: "2026-02-31" } });
    click("Search");
    await screen.findByText("Enter a valid date in YYYY-MM-DD format.");
    expect(requests).toHaveLength(count);
  });
});

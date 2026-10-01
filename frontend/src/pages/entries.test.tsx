import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import EntryListPage from "./EntryListPage";
import EntryCreatePage from "./EntryCreatePage";
import EntryDetailPage from "./EntryDetailPage";
import LoginPage from "./LoginPage";
import type { Entry } from "../api/entries";

const note: Entry = {
  id: 1, source: "manual", type: "NOTE", title: "여행 메모", content: "첫 줄\n둘째 줄",
  event_at: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
};
let records: Entry[];
let failedMethod: string | undefined;
let failureStatus: number;
let requests: { path: string; method: string }[];

beforeEach(() => {
  localStorage.clear();
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
          <Route path="/login" element={<LoginPage />} />
          <Route path="/entries" element={<EntryListPage />} />
          <Route path="/entries/new" element={<EntryCreatePage />} />
          <Route path="/entries/:id" element={<EntryDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

function click(text: string) { fireEvent.click(screen.getByText(text)); }
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
    mount("/entries?q=여행&source=manual&type=NOTE&date_field=event_at&date_from=2026-10-01&date_to=2026-10-02");
    await screen.findByRole("heading", { name: note.title });
    expect((screen.getByLabelText("Search query") as HTMLInputElement).value).toBe("여행");
    expect((screen.getByLabelText("Source") as HTMLSelectElement).value).toBe("manual");
    expect((screen.getByLabelText("Date field") as HTMLSelectElement).value).toBe("event_at");
    const firstPath = requests[0].path;
    expect(new URL(firstPath, "http://localhost").searchParams.get("date_to")).toBe("2026-10-02");
    click(note.title);
    await screen.findByText(/Source\/event date: Unknown/);
    click("← Back to entries");
    await screen.findByRole("heading", { name: note.title });
    expect((screen.getByLabelText("Search query") as HTMLInputElement).value).toBe("여행");
    expect(requests.at(-1)?.path).toBe(firstPath);
  });

  it("paginates without losing a query and resets the page on a new filter", async () => {
    records = Array.from({ length: 21 }, (_, i) => ({ ...note, id: i + 1, title: `메모 ${i + 1}` }));
    mount("/entries?q=메모");
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
    click("Reset");
    await waitFor(() => expect(requests.at(-1)?.path).toBe("/api/entries/search?limit=20"));
  });

  it("validates calendar ranges before applying and shows filtered empty results", async () => {
    mount("/entries?q=없는기록");
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
    mount("/entries?q=기록&offset=20");
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

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
  fireEvent.change(screen.getByLabelText("제목"), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("내용"), { target: { value: content } });
}

describe("Entry browser flow", () => {
  it("creates, lists, edits and deletes a note following server results", async () => {
    mount();
    await screen.findByText("저장된 Entry가 없어.");
    click("새 노트 작성");
    fill(" 여행 메모 ", "첫 줄\n둘째 줄");
    click("저장");
    await screen.findByRole("heading", { name: "여행 메모" });
    click("← 목록으로");
    await screen.findByRole("heading", { name: "여행 메모" });
    click("여행 메모");
    click("수정");
    expect((screen.getByLabelText("내용") as HTMLTextAreaElement).value).toBe("첫 줄\n둘째 줄");
    fill("수정한 메모", "");
    click("저장");
    await screen.findByRole("heading", { name: "수정한 메모" });
    click("← 목록으로");
    await screen.findByRole("heading", { name: "수정한 메모" });
    click("수정한 메모");
    click("삭제");
    click("취소");
    expect(requests.some((r) => r.method === "DELETE")).toBe(false);
    click("삭제");
    click("삭제 확인");
    await screen.findByText("저장된 Entry가 없어.");
  });

  it("rejects blank titles and preserves a draft when save fails", async () => {
    mount("/entries/new");
    fill("   ", "초안");
    click("저장");
    await screen.findByRole("alert");
    expect(requests).toHaveLength(0);
    fill("제목", "초안");
    failedMethod = "POST";
    click("저장");
    await screen.findByText(/요청 실패: 500/);
    expect((screen.getByLabelText("내용") as HTMLTextAreaElement).value).toBe("초안");
    failedMethod = undefined;
    click("저장");
    await screen.findByRole("heading", { name: "제목" });
  });

  it("keeps the server record and form on edit failure, and supports cancellation", async () => {
    records = [note];
    mount("/entries/1");
    await screen.findByRole("heading", { name: note.title });
    click("수정");
    fill("초안 수정", "내용 수정");
    failedMethod = "PATCH";
    failureStatus = 422;
    click("저장");
    await screen.findByText(/입력값/);
    expect(records[0].title).toBe(note.title);
    expect((screen.getByLabelText("제목") as HTMLInputElement).value).toBe("초안 수정");
    click("취소");
    await screen.findByRole("heading", { name: note.title });
  });

  it("keeps the detail visible on delete failure and allows retry", async () => {
    records = [note];
    mount("/entries/1");
    await screen.findByRole("heading", { name: note.title });
    click("삭제");
    failedMethod = "DELETE";
    click("삭제 확인");
    await screen.findByText(/요청 실패: 500/);
    expect(records).toHaveLength(1);
    failedMethod = undefined;
    click("삭제 확인");
    await screen.findByText("저장된 Entry가 없어.");
  });

  it("shows loading and a recoverable list error", async () => {
    failedMethod = "GET";
    mount();
    expect(screen.getByRole("status").textContent).toBe("불러오는 중...");
    await screen.findByRole("alert");
    failedMethod = undefined;
    click("다시 시도");
    await screen.findByText("저장된 Entry가 없어.");
  });

  it("shows a missing or inaccessible record", async () => {
    mount("/entries/99");
    await screen.findByText(/Entry를 찾을 수 없어/);
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
    click("로그인");
    await screen.findByText("저장된 Entry가 없어.");
    expect(queryClient.getQueryData(["entry", "1"])).toBeUndefined();
    expect(localStorage.getItem("access_token")).toBe("new-account-token");
  });

  it("explains an expired session", async () => {
    failedMethod = "GET";
    failureStatus = 401;
    mount();
    await screen.findByText("로그인이 만료됐어. 다시 로그인해 줘.");
  });

  it("disables resubmission while saving", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    mount("/entries/new");
    fill("제목", "내용");
    click("저장");
    await waitFor(() => expect((screen.getByLabelText("제목") as HTMLInputElement).disabled || screen.getByLabelText("제목").closest("fieldset")?.disabled).toBe(true));
    expect(screen.getByText("저장 중...")).toBeTruthy();
  });
});


describe("Entry search and pagination", () => {
  it("restores URL filters and preserves them through detail navigation", async () => {
    records = [note];
    mount("/entries?q=여행&source=manual&type=NOTE&date_field=event_at&date_from=2026-10-01&date_to=2026-10-02");
    await screen.findByRole("heading", { name: note.title });
    expect((screen.getByLabelText("검색어") as HTMLInputElement).value).toBe("여행");
    expect((screen.getByLabelText("출처") as HTMLSelectElement).value).toBe("manual");
    expect((screen.getByLabelText("날짜 기준") as HTMLSelectElement).value).toBe("event_at");
    const firstPath = requests[0].path;
    expect(new URL(firstPath, "http://localhost").searchParams.get("date_to")).toBe("2026-10-02");
    click(note.title);
    await screen.findByText(/원본\/사건 날짜: 알 수 없음/);
    click("← 목록으로");
    await screen.findByRole("heading", { name: note.title });
    expect((screen.getByLabelText("검색어") as HTMLInputElement).value).toBe("여행");
    expect(requests.at(-1)?.path).toBe(firstPath);
  });

  it("paginates without losing a query and resets the page on a new filter", async () => {
    records = Array.from({ length: 21 }, (_, i) => ({ ...note, id: i + 1, title: `메모 ${i + 1}` }));
    mount("/entries?q=메모");
    await screen.findByText("총 21개 · 1페이지");
    expect((screen.getByText("이전 페이지") as HTMLButtonElement).disabled).toBe(true);
    click("다음 페이지");
    await screen.findByText("총 21개 · 2페이지");
    expect(screen.queryByRole("heading", { name: "메모 1" })).toBeNull();
    expect((screen.getByText("다음 페이지") as HTMLButtonElement).disabled).toBe(true);
    const params = new URL(requests.at(-1)!.path, "http://localhost").searchParams;
    expect(params.get("q")).toBe("메모");
    expect(params.get("offset")).toBe("20");
    fireEvent.change(screen.getByLabelText("출처"), { target: { value: "manual" } });
    click("검색");
    await screen.findByText("총 21개 · 1페이지");
    expect(new URL(requests.at(-1)!.path, "http://localhost").searchParams.get("source")).toBe("manual");
    expect(new URL(requests.at(-1)!.path, "http://localhost").searchParams.has("offset")).toBe(false);
    click("초기화");
    await waitFor(() => expect(requests.at(-1)?.path).toBe("/api/entries/search?limit=20"));
  });

  it("validates calendar ranges before applying and shows filtered empty results", async () => {
    mount("/entries?q=없는기록");
    await screen.findByText("검색 조건에 맞는 기록이 없어.");
    const count = requests.length;
    fireEvent.change(screen.getByLabelText("시작일"), { target: { value: "2026-10-02" } });
    fireEvent.change(screen.getByLabelText("종료일"), { target: { value: "2026-10-01" } });
    click("검색");
    await screen.findByText("시작일은 종료일보다 늦을 수 없어.");
    expect(requests).toHaveLength(count);
  });

  it("moves back to the last existing page after deletion", async () => {
    records = Array.from({ length: 21 }, (_, i) => ({ ...note, id: i + 1, title: `기록 ${i + 1}` }));
    mount("/entries?q=기록&offset=20");
    await screen.findByRole("heading", { name: "기록 21" });
    click("기록 21");
    await screen.findByText("수정");
    click("삭제"); click("삭제 확인");
    await screen.findByText("총 20개 · 1페이지");
    await waitFor(() => expect(requests.at(-1)?.path).toBe("/api/entries/search?q=%EA%B8%B0%EB%A1%9D&limit=20"));
  });

  it("shows dates in Seoul even when the browser uses a different zone", async () => {
    records = [{ ...note, created_at: "2026-09-30T16:00:00Z" }];
    mount();
    await screen.findByText(/등록일: 2026. 10. 1. 오전 1:00/);
  });
});

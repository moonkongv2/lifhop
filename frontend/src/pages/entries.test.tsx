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
  id: 1, type: "NOTE", title: "여행 메모", content: "첫 줄\n둘째 줄",
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
      records = [];
      return new Response(null, { status: 204 });
    }
    if (path === "/api/entries") return Response.json(records);
    return records[0] ? Response.json(records[0]) : new Response(null, { status: 404 });
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
    await screen.findByText(/입력값을 확인/);
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
      return Response.json([]);
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

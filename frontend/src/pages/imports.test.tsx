import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import ImportsPage from "./ImportsPage";
import ImportJobPage from "./ImportJobPage";
import type { ImportJob } from "../api/imports";

let job: ImportJob;
let failPath: string | undefined;
let requests: { path: string; options: RequestInit }[];
const entry = { id: 7, title: "가져온 기록", content: "본문", type: "DOCUMENT", import_artifact_id: 2,
  event_at: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z" };

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("access_token", "test-token");
  failPath = undefined;
  requests = [];
  job = { id: 1, artifact_id: 2, status: "PENDING", attempts: 0, entry_ids: [], item_errors: [],
    total_items: 0, processed_items: 0, failed_items: 0, error: null,
    started_at: null, completed_at: null, created_at: "2026-10-01T00:00:00Z" };
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit = {}) => {
    requests.push({ path, options });
    expect((options.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
    if (path === failPath) return Response.json({ detail: "서비스 오류" }, { status: 503 });
    if (path === "/api/imports/markdown") return Response.json([entry]);
    if (path === "/api/imports/chatgpt") return Response.json({ job_id: 1, status: "PENDING" }, { status: 202 });
    if (path === "/api/import-jobs") return Response.json([job]);
    if (path === "/api/import-jobs/1") return Response.json(job);
    if (path === "/api/import-jobs/1/retry") {
      job = { ...job, status: "PENDING", error: null };
      return Response.json({ job_id: 1, status: "PENDING" }, { status: 202 });
    }
    if (path.startsWith("/api/import-jobs/1/entries")) return Response.json([entry]);
    if (path === "/api/import-artifacts/2/download") return Response.json({ download_url: "http://localhost:8333/signed-original" });
    throw new Error(`Unexpected request ${path}`);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function mount(path = "/imports") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  queryClient.setQueryData(["entries"], [entry]);
  queryClient.setQueryData(["entry", "7"], entry);
  render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/imports" element={<ImportsPage />} />
    <Route path="/import-jobs/:id" element={<ImportJobPage />} />
    <Route path="/login" element={<p>로그인 화면</p>} />
    <Route path="/entries/:id" element={<p>기록 상세</p>} />
  </Routes></MemoryRouter></QueryClientProvider>);
  return queryClient;
}
function chooseFile(name: string, body = "# Note") {
  fireEvent.change(screen.getByLabelText("파일"), { target: { files: [new File([body], name)] } });
}
function click(text: string) { fireEvent.click(screen.getByText(text)); }

describe("Browser imports", () => {
  it("uploads Markdown as multipart and exposes results and protected original", async () => {
    const client = mount();
    chooseFile("note.md");
    click("가져오기");
    await screen.findByText("가져오기 완료");
    expect(screen.getByText("가져온 기록").getAttribute("href")).toBe("/entries/7");
    const upload = requests.find((request) => request.path === "/api/imports/markdown")!;
    expect(upload.options.body).toBeInstanceOf(FormData);
    expect((upload.options.body as FormData).get("file")).toBeInstanceOf(File);
    expect(client.getQueryState(["entries"])?.isInvalidated).toBe(true);
    click("원본 다운로드 준비");
    await screen.findByText("원본 파일 다운로드");
    expect(screen.getByText("원본 파일 다운로드").getAttribute("href")).toBe("http://localhost:8333/signed-original");
  });

  it("uploads ZIP, polls status, and shows partial failures and results", async () => {
    mount();
    fireEvent.change(screen.getByLabelText("가져오기 종류"), { target: { value: "chatgpt" } });
    chooseFile("export.zip", "zip sample");
    click("가져오기");
    await screen.findByRole("heading", { name: "가져오기 작업 #1" });
    expect(screen.getByRole("status").textContent).toBe("대기 중");
    job = { ...job, status: "PARTIAL", attempts: 1, total_items: 2, processed_items: 1, failed_items: 1,
      entry_ids: [7], item_errors: [{ index: 2, code: "INVALID_ID", message: "Missing source identity" }] };
    await screen.findByText("일부 성공", {}, { timeout: 5000 });
    await screen.findByText("가져온 기록");
    expect(screen.getByText(/항목 2: Missing source identity/)).toBeTruthy();
    click("작업 재시도");
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("대기 중"));
    job = { ...job, status: "COMPLETED", attempts: 2, total_items: 2, processed_items: 2, failed_items: 0, item_errors: [] };
    await screen.findByText("완료", {}, { timeout: 5000 });
    expect(screen.queryByText("작업 재시도")).toBeNull();
  }, 10000);

  it("validates missing, wrong-type, and empty files without uploading", async () => {
    mount();
    click("가져오기");
    await screen.findByText("내용이 있는 파일을 선택해 줘.");
    chooseFile("image.png");
    click("가져오기");
    await screen.findByText("선택한 가져오기 종류에 맞는 파일을 선택해 줘.");
    chooseFile("empty.md", "");
    click("가져오기");
    await screen.findByText("내용이 있는 파일을 선택해 줘.");
    expect(requests.some((request) => request.options.method === "POST")).toBe(false);
  });

  it("shows upload errors and lets the selected file be retried", async () => {
    mount();
    chooseFile("note.md");
    failPath = "/api/imports/markdown";
    click("가져오기");
    await screen.findByText("서비스 오류");
    failPath = undefined;
    click("가져오기");
    await screen.findByText("가져오기 완료");
  });

  it("resumes a completed job by URL and invalidates stale Entry caches", async () => {
    job = { ...job, status: "COMPLETED", attempts: 1, entry_ids: [7], processed_items: 1, total_items: 1 };
    const client = mount("/import-jobs/1");
    await screen.findByText("가져온 기록");
    expect(client.getQueryState(["entry", "7"])?.isInvalidated).toBe(true);
    expect(screen.getByText("가져온 기록").getAttribute("href")).toBe("/entries/7");
  });

  it("shows failed-job details and retry conflicts without hiding results", async () => {
    job = { ...job, status: "FAILED", error: "Invalid ZIP archive", attempts: 3 };
    failPath = "/api/import-jobs/1/retry";
    mount("/import-jobs/1");
    await screen.findByText("Invalid ZIP archive");
    click("작업 재시도");
    await screen.findByText("서비스 오류");
    expect(screen.getByRole("status").textContent).toBe("실패");
  });

  it("shows protected-download errors and supports another request", async () => {
    mount("/import-jobs/1");
    await screen.findByRole("heading", { name: "가져오기 작업 #1" });
    failPath = "/api/import-artifacts/2/download";
    click("원본 다운로드 준비");
    await screen.findByText("서비스 오류");
    failPath = undefined;
    click("원본 다운로드 준비");
    await screen.findByText("원본 파일 다운로드");
  });

  it("shows an inaccessible job and a retry button", async () => {
    failPath = "/api/import-jobs/1";
    mount("/import-jobs/1");
    await screen.findByRole("alert");
    failPath = undefined;
    click("다시 시도");
    await screen.findByRole("heading", { name: "가져오기 작업 #1" });
  });

  it("redirects unauthenticated visitors without any API request", async () => {
    localStorage.clear();
    mount();
    await screen.findByText("로그인 화면");
    expect(requests).toHaveLength(0);
  });
});


it("displays saved progress while a large import is still running", async () => {
  job = { ...job, status: "RUNNING", attempts: 1, total_items: 1284, processed_items: 25 };
  mount("/import-jobs/1");
  await screen.findByText("전체 1284 / 성공 25 / 실패 0 / 시도 1");
  expect(screen.getByText(/저장된 처리 건수를 자동 확인/)).toBeTruthy();
  expect(screen.queryByText("작업 재시도")).toBeNull();
  job = { ...job, processed_items: 50 };
  await screen.findByText("전체 1284 / 성공 50 / 실패 0 / 시도 1", {}, { timeout: 5000 });
});

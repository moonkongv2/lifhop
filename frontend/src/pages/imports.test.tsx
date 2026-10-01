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
    if (path === failPath) return Response.json({ detail: "Service unavailable" }, { status: 503 });
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
    <Route path="/login" element={<p>Login page</p>} />
    <Route path="/entries/:id" element={<p>Entry detail</p>} />
  </Routes></MemoryRouter></QueryClientProvider>);
  return queryClient;
}
function chooseFile(name: string, body = "# Note") {
  fireEvent.change(screen.getByLabelText("File"), { target: { files: [new File([body], name)] } });
}
function click(text: string) { fireEvent.click(screen.getByText(text)); }

describe("Browser imports", () => {
  it("uploads Markdown as multipart and exposes results and protected original", async () => {
    const client = mount();
    chooseFile("note.md");
    click("Import");
    await screen.findByText("Import complete");
    expect(screen.getByText("가져온 기록").getAttribute("href")).toBe("/entries/7");
    const upload = requests.find((request) => request.path === "/api/imports/markdown")!;
    expect(upload.options.body).toBeInstanceOf(FormData);
    expect((upload.options.body as FormData).get("file")).toBeInstanceOf(File);
    expect(client.getQueryState(["entries"])?.isInvalidated).toBe(true);
    click("Prepare original download");
    await screen.findByText("Download original file");
    expect(screen.getByText("Download original file").getAttribute("href")).toBe("http://localhost:8333/signed-original");
  });

  it("uploads ZIP, polls status, and shows partial failures and results", async () => {
    mount();
    fireEvent.change(screen.getByLabelText("Import type"), { target: { value: "chatgpt" } });
    chooseFile("export.zip", "zip sample");
    click("Import");
    await screen.findByRole("heading", { name: "Import job #1" });
    expect(screen.getByRole("status").textContent).toBe("Pending");
    job = { ...job, status: "PARTIAL", attempts: 1, total_items: 2, processed_items: 1, failed_items: 1,
      entry_ids: [7], item_errors: [{ index: 2, code: "INVALID_ID", message: "Missing source identity" }] };
    await screen.findByText("Partially completed", {}, { timeout: 5000 });
    await screen.findByText("가져온 기록");
    expect(screen.getByText(/Item 2: Missing source identity/)).toBeTruthy();
    click("Retry job");
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("Pending"));
    job = { ...job, status: "COMPLETED", attempts: 2, total_items: 2, processed_items: 2, failed_items: 0, item_errors: [] };
    await screen.findByText("Completed", {}, { timeout: 5000 });
    expect(screen.queryByText("Retry job")).toBeNull();
  }, 10000);

  it("validates missing, wrong-type, and empty files without uploading", async () => {
    mount();
    click("Import");
    await screen.findByText("Please select a non-empty file.");
    chooseFile("image.png");
    click("Import");
    await screen.findByText("Please select a file that matches the import type.");
    chooseFile("empty.md", "");
    click("Import");
    await screen.findByText("Please select a non-empty file.");
    expect(requests.some((request) => request.options.method === "POST")).toBe(false);
  });

  it("shows upload errors and lets the selected file be retried", async () => {
    mount();
    chooseFile("note.md");
    failPath = "/api/imports/markdown";
    click("Import");
    await screen.findByText("Service unavailable");
    failPath = undefined;
    click("Import");
    await screen.findByText("Import complete");
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
    click("Retry job");
    await screen.findByText("Service unavailable");
    expect(screen.getByRole("status").textContent).toBe("Failed");
  });

  it("shows protected-download errors and supports another request", async () => {
    mount("/import-jobs/1");
    await screen.findByRole("heading", { name: "Import job #1" });
    failPath = "/api/import-artifacts/2/download";
    click("Prepare original download");
    await screen.findByText("Service unavailable");
    failPath = undefined;
    click("Prepare original download");
    await screen.findByText("Download original file");
  });

  it("shows an inaccessible job and a retry button", async () => {
    failPath = "/api/import-jobs/1";
    mount("/import-jobs/1");
    await screen.findByRole("alert");
    failPath = undefined;
    click("Retry");
    await screen.findByRole("heading", { name: "Import job #1" });
  });

  it("redirects unauthenticated visitors without any API request", async () => {
    localStorage.clear();
    mount();
    await screen.findByText("Login page");
    expect(requests).toHaveLength(0);
  });
});


it("displays saved progress while a large import is still running", async () => {
  job = { ...job, status: "RUNNING", attempts: 1, total_items: 1284, processed_items: 25 };
  mount("/import-jobs/1");
  await screen.findByText("Total 1284 / Saved 25 / Failed 0 / Attempts 1");
  expect(screen.getByText(/saved progress update automatically/)).toBeTruthy();
  expect(screen.queryByText("Retry job")).toBeNull();
  job = { ...job, processed_items: 50 };
  await screen.findByText("Total 1284 / Saved 50 / Failed 0 / Attempts 1", {}, { timeout: 5000 });
});

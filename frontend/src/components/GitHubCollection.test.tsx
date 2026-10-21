import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GitHubCollection from "./GitHubCollection";

let registered: boolean;
let active: boolean;
let calls: { path: string; body: unknown }[];
let fail: boolean;
let scheduleEnabled: boolean;
let intervalSeconds: number;
let failedJob: boolean;
let discussionSelection: { enabled: boolean; exclude_numbers: number[] };

beforeEach(() => {
  registered = false; active = false; calls = []; fail = false;
  scheduleEnabled = false; intervalSeconds = 900; failedJob = false;
  discussionSelection = { enabled: false, exclude_numbers: [] };
  localStorage.setItem("access_token", "synthetic-token");
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit = {}) => {
    const body = options.body ? JSON.parse(options.body as string) : undefined;
    calls.push({ path, body });
    if (fail) return Response.json({ detail: "Source has an active manual backfill" }, { status: 409 });
    if (path === "/api/collection-subscriptions" && options.method === "POST") {
      registered = true; return Response.json({ id: 1 });
    }
    if (path.endsWith("/collect-now")) { active = true; return Response.json({ id: 7, status: "pending" }); }
    if (path.endsWith("/cancel")) { active = false; return Response.json({ id: 1 }); }
    if (path.endsWith("/schedule")) {
      expect(options.method).toBe("PATCH");
      scheduleEnabled = body.enabled; intervalSeconds = body.interval_seconds;
      if (!scheduleEnabled) active = false;
      return Response.json({ id: 1 });
    }
    if (path.endsWith("/retry")) { active = true; failedJob = false; return Response.json({ id: 7 }); }
    if (path.endsWith("/discussions")) {
      expect(options.method).toBe("PATCH");
      discussionSelection = body; scheduleEnabled = false; active = false;
      return Response.json({ id: 1 });
    }
    return Response.json(registered ? [{ id: 1, scope: "repo:123", provider: "github", revision: 1,
      config: { repository: "example/repo", repository_id: 123, branches: ["main"] },
      discussion_selection: discussionSelection,
      incremental: { branches: { main: { observed_head: "a".repeat(40), completed_head: null, documents_head: "a".repeat(40), pending_steps: 2 } },
        known_threads: 4, unchecked_threads: 1, pending_threads: 2, inventory_page: 3,
        inventory_completed_at: null, oldest_thread_check: null },
      last_checked_at: null, last_success_at: null,
      schedule_enabled: scheduleEnabled, interval_seconds: intervalSeconds,
      next_due_at: scheduleEnabled ? "2026-10-22T01:00:00Z" : null, schedule_error: failedJob ? "AUTH_FAILED" : null,
      job: failedJob ? { id: 7, status: "failed", attempts: 1, error_code: "AUTH_FAILED" }
        : active ? { id: 7, status: "pending", run_id: null, attempts: 1, retry_at: "2026-10-22T01:00:00Z" } : null }] : []);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

function mount(allowed = true) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <GitHubCollection policies={[{ id: 2, provider: "github", scope: "repo:123", collection_enabled: allowed, external_ai_allowed: false }]} />
  </QueryClientProvider>);
}

it("registers exact selection without collecting, then explicitly queues and cancels one job", async () => {
  mount();
  fireEvent.change(screen.getByLabelText("Repository (owner/name)"), { target: { value: "example/repo" } });
  fireEvent.change(screen.getByLabelText("Repository ID"), { target: { value: "123" } });
  fireEvent.change(screen.getByLabelText("Excluded paths (comma separated)"), { target: { value: "private/**" } });
  fireEvent.click(screen.getByRole("button", { name: "Register GitHub source" }));
  await screen.findByText("example/repo · repo:123");
  expect(calls.some(c => c.path.endsWith("/collect-now"))).toBe(false);
  expect(calls.find(c => c.body)?.body).toMatchObject({ config: { repository: "example/repo", repository_id: 123, exclude_paths: ["private/**"] } });
  fireEvent.click(screen.getByRole("button", { name: "Collect now" }));
  await screen.findByText(/Job #7: pending/);
  expect(screen.getByRole("button", { name: "Collect now" }).hasAttribute("disabled")).toBe(true);
  expect(calls.find(c => c.path.endsWith("/collect-now"))?.body).toMatchObject({ request_id: expect.any(String) });
  fireEvent.click(screen.getByRole("button", { name: "Cancel collection" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: "Cancel collection" })).toBeNull());
});

it("honors disabled source policy and displays recoverable API errors", async () => {
  registered = true;
  mount(false);
  await screen.findByText("example/repo · repo:123");
  expect(screen.getByRole("button", { name: "Collect now" }).hasAttribute("disabled")).toBe(true);
  fail = true;
  fireEvent.change(screen.getByLabelText("Repository (owner/name)"), { target: { value: "example/repo" } });
  fireEvent.change(screen.getByLabelText("Repository ID"), { target: { value: "123" } });
  fireEvent.click(screen.getByRole("button", { name: "Register GitHub source" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Source has an active manual backfill");
});

it("enables and pauses a schedule with an explicit interval without collecting immediately", async () => {
  registered = true;
  mount();
  const interval = await screen.findByLabelText("Schedule interval in seconds for repo:123");
  fireEvent.change(interval, { target: { value: "60" } });
  fireEvent.click(screen.getByRole("button", { name: "Enable schedule" }));
  await screen.findByRole("button", { name: "Update schedule" });
  expect(calls.find(c => c.path.endsWith("/schedule"))?.body).toEqual({ enabled: true, interval_seconds: 60 });
  expect(calls.some(c => c.path.endsWith("/collect-now"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Pause schedule" }));
  await screen.findByRole("button", { name: "Enable schedule" });
  expect(calls.filter(c => c.path.endsWith("/schedule")).at(-1)?.body).toEqual({ enabled: false, interval_seconds: 60 });
});

it("shows a failed job and retries it while leaving the schedule paused", async () => {
  registered = true; failedJob = true;
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Retry failed job" }));
  await screen.findByText(/Job #7: pending/);
  expect(calls.some(c => c.path.endsWith("/retry"))).toBe(true);
  expect(screen.getByRole("button", { name: "Enable schedule" })).toBeTruthy();
  expect(screen.getByText(/Next retry:/)).toBeTruthy();
});

it("requires an explicit discussion selection and shows pending graph/thread coverage", async () => {
  registered = true; scheduleEnabled = true; active = true;
  mount();
  const toggle = await screen.findByLabelText("Collect PRs, issues, comments and reviews for repo:123");
  expect((toggle as HTMLInputElement).checked).toBe(false);
  fireEvent.click(toggle);
  fireEvent.change(screen.getByLabelText("Excluded PR/issue numbers for repo:123"), { target: { value: "7, 9" } });
  fireEvent.click(screen.getByRole("button", { name: "Save discussion selection" }));
  await screen.findByRole("button", { name: "Enable schedule" });
  expect(calls.find(c => c.path.endsWith("/discussions"))?.body).toEqual({ enabled: true, exclude_numbers: [7, 9] });
  expect(screen.getByText(/pending steps 2/)).toBeTruthy();
  expect(screen.getByText(/4 known, 1 unchecked/)).toBeTruthy();
  expect(calls.some(c => c.path.endsWith("/collect-now"))).toBe(false);
});

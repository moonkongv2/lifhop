import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import SourcesPage from "./SourcesPage";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

it("keeps GitHub controls, offline Mac work and collection receipts distinct on Sources", async () => {
  localStorage.setItem("access_token", "synthetic-owner");
  const writes: string[] = [];
  let disconnected = false;
  const common = { revision: 1, interval_seconds: 300, schedule_enabled: true,
    next_due_at: "2026-10-22T01:00:00Z", last_checked_at: null, last_success_at: null };
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit = {}) => {
    if (options.method !== "GET") {
      writes.push(path);
      if (path === "/api/codex-subscriptions/2/disconnect") { disconnected = true; return Response.json({ id: 2 }); }
      return Response.json({ detail: "Unexpected write" }, { status: 400 });
    }
    if (path === "/api/sources") return Response.json([
      { id: 11, provider: "github", scope: "repo:123", collection_enabled: true, external_ai_allowed: false },
      { id: 12, provider: "codex", scope: "mac:synthetic", collection_enabled: true, external_ai_allowed: false },
    ]);
    if (path === "/api/collection-subscriptions") return Response.json([{ ...common, id: 1,
      provider: "github", scope: "repo:123", config: { repository: "example/repo", branches: ["main"] },
      discussion_selection: { enabled: false, exclude_numbers: [] }, schedule_enabled: false,
      incremental: { branches: {}, known_threads: 0, unchecked_threads: 0, pending_threads: 0,
        inventory_page: 1, inventory_completed_at: null, oldest_thread_check: null },
      schedule_error: "AUTH_FAILED", job: { id: 10, status: "failed", attempts: 1, error_code: "AUTH_FAILED" } }]);
    if (path === "/api/codex-subscriptions") return Response.json([{ ...common, id: 2,
      provider: "codex", scope: "mac:synthetic", config: { include_cwd: ["/synthetic/project"], threads: [] },
      schedule_enabled: !disconnected, schedule_error: disconnected ? "CREDENTIAL_REVOKED" : null,
      agent_status: "offline", agent_seen_at: null, rotation_offset: 3, deferred: 1, failed: 0, credentials: [],
      job: { id: 20, status: disconnected ? "cancelled" : "pending", attempts: 0 } }]);
    if (path.startsWith("/api/collection-runs?")) return Response.json([]);
    if (path === "/api/sources/suppressed/records") return Response.json([]);
    if (path === "/api/sources/purges/status") return Response.json({ pending: 0, failed_attempts: 0, errors: [] });
    return Response.json({ detail: "Unexpected read" }, { status: 404 });
  }));
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter><SourcesPage /></MemoryRouter></QueryClientProvider>);
  const github = within(screen.getByRole("region", { name: "GitHub collect now" }));
  const codex = within(screen.getByRole("region", { name: "Codex device collection" }));
  await github.findByText(/Job #10: failed/);
  await codex.findByText(/Job #20: pending/);
  expect(github.getAllByText(/AUTH_FAILED/, { selector: "p" }).length).toBeGreaterThan(0);
  expect(codex.getByText(/Agent: offline/)).toBeTruthy();
  expect(codex.getByText(/Deferred threads: 1/)).toBeTruthy();
  expect(codex.getByRole("button", { name: "Collect device now" }).hasAttribute("disabled")).toBe(true);
  expect(screen.getAllByLabelText("Allow external AI for this source").every(
    box => !(box as HTMLInputElement).checked)).toBe(true);
  expect(screen.getByText(/These receipts include manual history imports and scheduled collection/)).toBeTruthy();
  expect(screen.queryByText(/Collection is manual/)).toBeNull();
  fireEvent.change(screen.getByLabelText("Collection source"), { target: { value: "github" } });
  await screen.findByRole("region", { name: "GitHub collection batches" });
  fireEvent.click(codex.getByRole("button", { name: "Disconnect device" }));
  await waitFor(() => expect(codex.getByText(/Job #20: cancelled/)).toBeTruthy());
  expect(github.getByText(/Job #10: failed/)).toBeTruthy();
  expect(writes).toEqual(["/api/codex-subscriptions/2/disconnect"]);
});

import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SourceIndexingStatus from "./SourceIndexingStatus";
import type { Policy } from "../api/history";

const policies: Policy[] = [{ id: 1, provider: "github", scope: "repo:123", collection_enabled: true, external_ai_allowed: false },
  { id: 2, provider: "codex", scope: "mac:demo", collection_enabled: true, external_ai_allowed: true }];
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });
function mount() {
  localStorage.setItem("access_token", "synthetic-owner");
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <SourceIndexingStatus policies={policies} />
  </QueryClientProvider>);
}

it("shows scoped indexing counts and uncertainty without starting or retrying AI", async () => {
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit) => {
    requests.push(`${options.method} ${path}`);
    return Response.json([
      { id: "run-a", provider: "github", scope: "repo:123", status: "completed", follow_changes: false,
        counts: { completed: 2, failed: 1, uncertain: 1 }, error_code: "INDEXING_DISPATCH_UNCERTAIN" },
      { id: "other-scope", provider: "github", scope: "repo:999", status: "active", counts: {} },
    ]);
  }));
  mount();
  await screen.findByText(/Indexing run run-a: completed/);
  expect(screen.getByText(/2 completed · 1 failed · 1 uncertain/)).toBeTruthy();
  expect(screen.getByText(/uncertain outcome/)).toBeTruthy();
  expect(screen.getByText(/disabled; new AI work is blocked/)).toBeTruthy();
  expect(screen.getByText(/No indexing runs for this source in the returned recent history/)).toBeTruthy();
  expect(screen.queryByText(/other-scope/)).toBeNull();
  expect(screen.getByText(/latest 50 registered indexing runs/)).toBeTruthy();
  expect(requests).toEqual(["GET /api/indexing/runs"]);
  expect(screen.queryByRole("button")).toBeNull();
});

it("keeps an unavailable status distinct from an empty run list and retries only the read", async () => {
  let fail = true;
  const fetcher = vi.fn(async (_path: string, options: RequestInit) => {
    expect(options.method).toBe("GET");
    return fail ? Response.json({ detail: "INDEXING_DATABASE_UNAVAILABLE" }, { status: 503 }) : Response.json([]);
  });
  vi.stubGlobal("fetch", fetcher);
  mount();
  await screen.findByRole("alert");
  expect(screen.queryByText(/No indexing runs for this source/)).toBeNull();
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Retry loading indexing status" }));
  await screen.findAllByText(/No indexing runs for this source/);
  expect(screen.queryByRole("alert")).toBeNull();
  expect(fetcher).toHaveBeenCalledTimes(2);
});

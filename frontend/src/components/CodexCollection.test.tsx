import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CodexCollection from "./CodexCollection";

const device = "11111111-1111-4111-8111-111111111111";
const token = "lhc_" + "T".repeat(43);
let registered: boolean;
let active: boolean;
let scheduled: boolean;
let revoked: boolean;
let revision: number;
let calls: { path: string; data: unknown; method: string }[];
let fail: boolean;

beforeEach(() => {
  registered = false; active = false; scheduled = false; revoked = false; revision = 1; calls = []; fail = false;
  localStorage.setItem("access_token", "synthetic-login");
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit = {}) => {
    const data = options.body ? JSON.parse(options.body as string) : undefined;
    const method = options.method ?? "GET";
    calls.push({ path, data, method });
    if (fail) return Response.json({ detail: "Select at least one CWD or thread" }, { status: 422 });
    if (path === "/api/codex-subscriptions" && method === "POST") { registered = true; return Response.json({ id: 1 }); }
    if (path.endsWith("/credentials") && method === "POST") {
      scheduled = false; active = false;
      return Response.json({ credential: { id: 5 }, token });
    }
    if (path.endsWith("/collect-now")) { active = true; return Response.json({ id: 9 }); }
    if (path.endsWith("/schedule")) { scheduled = data.enabled; if (!scheduled) active = false; return Response.json({ id: 1 }); }
    if (path.endsWith("/selection")) { revision += 1; scheduled = false; active = false; return Response.json({ id: 1 }); }
    if (path.endsWith("/disconnect")) { revoked = true; scheduled = false; active = false; return Response.json({ id: 1 }); }
    if (path.includes("/credentials/")) { revoked = true; return new Response(null, { status: 204 }); }
    return Response.json(registered ? [{ id: 1, provider: "codex", scope: "mac:"+device, revision,
      config: { device_uuid: device, include_cwd: ["/synthetic/project"], threads: [], exclude_cwd: [], exclude_thread: [] },
      interval_seconds: 300, schedule_enabled: scheduled, next_due_at: null, schedule_error: null,
      last_checked_at: null, last_success_at: null, agent_seen_at: null, agent_status: "offline",
      rotation_offset: 2, deferred: 1, failed: 0,
      job: active ? { id: 9, status: "pending", attempts: 0, error_code: null } : null,
      credentials: [{ id: 5, expires_at: "2026-11-22T00:00:00Z", revoked_at: revoked ? "2026-10-22T00:00:00Z" : null }],
    }] : []);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

function mount(allowed = true) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><CodexCollection policies={[{ id: 2, provider: "codex",
    scope: "mac:"+device, collection_enabled: allowed, external_ai_allowed: false }]} /></QueryClientProvider>);
  return cache;
}

it("registers an exact device selection without starting collection or issuing credentials", async () => {
  mount();
  fireEvent.change(screen.getByLabelText("Device UUID"), { target: { value: device } });
  fireEvent.change(screen.getByLabelText("Selected CWD roots (one per line)"), { target: { value: "/synthetic/project" } });
  fireEvent.click(screen.getByRole("button", { name: "Register Codex device" }));
  await screen.findByText("Device mac:"+device);
  expect(calls.find(call => call.method === "POST")?.data).toEqual({ config: { device_uuid: device, include_cwd: ["/synthetic/project"], threads: [] } });
  expect(calls.some(call => call.path.endsWith("/collect-now") || call.path.endsWith("/credentials"))).toBe(false);
});

it("displays a token once without persisting it in storage or server-state caches", async () => {
  registered = true;
  const cache = mount();
  fireEvent.click(await screen.findByRole("button", { name: "Issue or rotate device token" }));
  expect((await screen.findByLabelText("One-time collector token") as HTMLTextAreaElement).value).toBe(token);
  expect(JSON.stringify(cache.getQueryCache().getAll().map(query => query.state.data))).not.toContain(token);
  expect(JSON.stringify(cache.getMutationCache().getAll().map(mutation => mutation.state.data))).not.toContain(token);
  expect(JSON.stringify(localStorage)).not.toContain(token);
  fireEvent.click(screen.getByRole("button", { name: "Hide collector token" }));
  expect(screen.queryByLabelText("One-time collector token")).toBeNull();
});

it("queues offline work, enables a schedule and pauses it explicitly", async () => {
  registered = true;
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Collect device now" }));
  await screen.findByText(/Job #9: pending/);
  expect(screen.getByText(/Agent: offline/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Interval in seconds for device 1"), { target: { value: "60" } });
  fireEvent.click(screen.getByRole("button", { name: "Enable or update device schedule" }));
  await screen.findByText(/Schedule: enabled/);
  expect(calls.find(call => call.path.endsWith("/schedule"))?.data).toEqual({ enabled: true, interval_seconds: 60 });
  fireEvent.click(screen.getByRole("button", { name: "Pause device schedule" }));
  await screen.findByText(/Schedule: paused/);
  await waitFor(() => expect(screen.queryByText(/Job #9/)).toBeNull());
});

it("edits selection explicitly and disconnects without granting AI permission", async () => {
  registered = true;
  mount();
  const selected = await screen.findByLabelText("Selected threads for device 1");
  fireEvent.change(selected, { target: { value: "only-this-thread" } });
  fireEvent.click(screen.getByRole("button", { name: "Save device selection" }));
  await waitFor(() => expect(calls.some(call => call.path.endsWith("/selection"))).toBe(true));
  expect(calls.find(call => call.path.endsWith("/selection"))?.data).toMatchObject({ config: { threads: ["only-this-thread"] } });
  await waitFor(() => expect(screen.getByRole("button", { name: "Disconnect device" }).hasAttribute("disabled")).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Disconnect device" }));
  await screen.findByText(/Revoked/);
  expect(calls.some(call => JSON.stringify(call.data ?? null).includes("external_ai_allowed"))).toBe(false);
});

it("honors disabled collection and surfaces configuration errors", async () => {
  registered = true;
  mount(false);
  expect((await screen.findByRole("button", { name: "Collect device now" })).hasAttribute("disabled")).toBe(true);
  fail = true;
  fireEvent.click(screen.getByRole("button", { name: "Issue or rotate device token" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Select at least one CWD or thread");
});

import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import CollectionRecovery from "./CollectionRecovery";
import type { components } from "../api/generated/schema";

type Source = components["schemas"]["CodexSubscriptionResponse"];
const source = { provider: "codex", scope: "mac:demo", agent_status: "offline",
  schedule_enabled: false, schedule_error: null, job: null } as Source;
const pending = { id: 1, status: "pending", attempts: 0, retry_at: null, error_code: null } as NonNullable<Source["job"]>;
afterEach(() => { cleanup(); vi.useRealTimers(); });

it("keeps an offline manual request queued even when scheduling is paused", () => {
  render(<CollectionRecovery source={{ ...source, job: pending }} allowed />);
  expect(screen.getByText("Collection status: Queued.")).toBeTruthy();
  expect(screen.getByText(/An offline device does not mean collection failed/)).toBeTruthy();
  expect(screen.getByText(/Next action: Keep the selected Mac agent running/)).toBeTruthy();
  expect(screen.queryByText("Collection status: Schedule paused.")).toBeNull();
});

it("shows the retry time and preserves bounded waiting rather than urging an immediate retry", () => {
  render(<CollectionRecovery source={{ ...source, schedule_enabled: true,
    job: { ...pending, attempts: 1, error_code: "TIMEOUT", retry_at: "2026-10-22T01:00:00Z" } }} allowed />);
  expect(screen.getByText("Collection status: Retry scheduled.")).toBeTruthy();
  expect(screen.getByText(/Retry eligible from:/)).toBeTruthy();
  expect(screen.getByText(/Next action: A collection attempt timed out/)).toBeTruthy();
});

it("stops recommending automatic retry once a transient failure is terminal", () => {
  render(<CollectionRecovery source={{ ...source, schedule_error: "RETRY_EXHAUSTED",
    job: { ...pending, status: "failed", attempts: 4, error_code: "TIMEOUT" } }} allowed />);
  expect(screen.getByText("Collection status: Collection failed.")).toBeTruthy();
  expect(screen.getByText(/Next action: Automatic attempts have stopped/)).toBeTruthy();
});

it("prioritizes the current pending job over a previous schedule failure", () => {
  render(<CollectionRecovery source={{ ...source, schedule_error: "RETRY_EXHAUSTED", job: pending }} allowed />);
  expect(screen.getByText(/Next action: Keep the selected Mac agent running/)).toBeTruthy();
  expect(screen.queryByText(/Automatic attempts have stopped/)).toBeNull();
});

it("requires a replacement token after expiry instead of treating offline as the only problem", () => {
  render(<CollectionRecovery source={{ ...source, schedule_error: "CREDENTIAL_EXPIRED",
    job: { ...pending, status: "cancelled", error_code: "CREDENTIAL_EXPIRED" } }} allowed />);
  expect(screen.getByText("Collection status: Needs attention.")).toBeTruthy();
  expect(screen.getByText(/Next action: Issue a replacement device token/)).toBeTruthy();
});

it("shows partial gaps and directs a new collection rather than a frozen failed-job retry", () => {
  render(<CollectionRecovery source={{ ...source, job: { ...pending, status: "partial" } }} allowed />);
  expect(screen.getByText("Collection status: Partially collected.")).toBeTruthy();
  expect(screen.getByText(/Next action: Inspect the collection batch gaps/)).toBeTruthy();
});

it("distinguishes unavailable policy data from an explicit collection denial", () => {
  const view = render(<CollectionRecovery source={source} allowed={undefined} />);
  expect(screen.getByText("Collection status: Collection permission unavailable.")).toBeTruthy();
  view.rerender(<CollectionRecovery source={source} allowed={false} />);
  expect(screen.getByText("Collection status: Collection disabled.")).toBeTruthy();
  expect(screen.getByText(/Next action: Enable Allow collection/)).toBeTruthy();
});

it("shows lease expiry while the page stays open and accepts a renewed lease without cancelling work", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-10-22T01:00:00Z'));
  const running = { ...source, agent_status: "online" as const, job: { ...pending, status: "running",
    lease_until: '2026-10-22T01:00:10Z' } };
  const view = render(<CollectionRecovery source={running} allowed />);
  expect(screen.getByText("Collection status: Collecting.")).toBeTruthy();
  act(() => { vi.advanceTimersByTime(15000); });
  expect(screen.getByText("Collection status: Reported lease expired — check worker.")).toBeTruthy();
  expect(screen.getByText(/Next action: Check or restart the selected Mac agent/)).toBeTruthy();
  expect(screen.getByText(/This does not prove the process has stopped/)).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
  view.rerender(<CollectionRecovery source={{ ...running, job: { ...running.job,
    lease_until: '2026-10-22T01:01:45Z' } }} allowed />);
  expect(screen.getByText("Collection status: Collecting.")).toBeTruthy();
  expect(screen.queryByText(/Next action: Check or restart/)).toBeNull();
});

it("does not report a cancelled job as expired even if its old lease remains", () => {
  render(<CollectionRecovery source={{ ...source, job: { ...pending, status: "cancelled",
    lease_until: '2020-01-01T00:00:00Z' } }} allowed />);
  expect(screen.getByText("Collection status: Schedule paused.")).toBeTruthy();
  expect(screen.queryByText(/Reported lease expired/)).toBeNull();
});

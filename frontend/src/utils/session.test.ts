import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchEntry } from "../api/entries";
import { fetchJobs } from "../api/imports";
import { historyRequest } from "../api/history";
import { clearSession, setAccessToken } from "./session";

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); setAccessToken("old-token"); });
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });
const requests = [() => fetchEntry("1"), () => fetchJobs(), () => historyRequest("/sources")];

describe("Session boundaries", () => {
  it.each(requests)("clears an expired session for each API client", async request => {
    localStorage.setItem("refresh_token", "old-refresh");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 401 })));
    await expect(request()).rejects.toThrow("Your session has expired.");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(sessionStorage.getItem("session_notice")).toContain("Please log in again.");
  });
  it.each(requests)("rejects a late success after logout", async request => {
    let finish!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })));
    const pending = request();
    clearSession();
    finish(Response.json({ private: "synthetic" }));
    await expect(pending).rejects.toThrow("Your session has changed.");
  });
  it("does not clear a new account when an old request returns 401", async () => {
    let finish!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })));
    const pending = fetchEntry("1");
    setAccessToken("new-token");
    finish(new Response(null, { status: 401 }));
    await expect(pending).rejects.toThrow("Your session has expired.");
    expect(localStorage.getItem("access_token")).toBe("new-token");
    expect(sessionStorage.getItem("session_notice")).toBeNull();
  });
});

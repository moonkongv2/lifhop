import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import ConversationPage from "./ConversationPage";
import ConversationsPage from "./ConversationsPage";
import SavedQuestion from "../components/SavedQuestion";
import { setAccessToken } from "../utils/session";

const id = "a".repeat(32), tid = "b".repeat(32);
const savedTurn = { id: tid, seq: 1, request_id: "c".repeat(32), epoch: 0, q: "Original question", base_turn_id: null,
  state: "completed", outcome: "answer", branch: "search", answer: "Saved answer from the original record.", answer_status: "supported",
  error_code: null, availability: "available", citations: [{ entry_id: 4, version_id: 7, field: "content", start: 0, end: 10, passage_hash: "d".repeat(64) }],
  context_summary: {}, usage: [{ purpose: "answer", status: "spent" }], lease_expires_at: null, action_expires_at: "2026-10-20" };
let data: Record<string, unknown>;
let requests: { path: string; method: string }[];
let enabled: boolean;
beforeEach(() => {
  localStorage.clear(); setAccessToken("owner-token"); enabled = true; requests = [];
  data = { id, title: "My saved chat", state: "active", revision: 4, updated_at: "2026-10-20", filters: {}, turns: [savedTurn], next_before: null, unfinished: null };
  vi.stubGlobal("fetch", vi.fn(async (path: string, init: RequestInit = {}) => {
    const method = init.method ?? "GET"; requests.push({ path, method });
    if (path.endsWith("/answers/status")) return Response.json({ enabled, policy_revision: 1 });
    if (path === "/api/answer-conversations" && method === "GET") return Response.json({ items: [data], next_cursor: null });
    if (path === "/api/answer-conversations" && method === "POST") return Response.json({ ...data, turns: [] });
    if (path.endsWith("/turns")) {
      const q = JSON.parse(init.body as string).q;
      data = { ...data, revision: 5, turns: [savedTurn, { ...savedTurn, id: "e".repeat(32), q, state: "created", answer: null }], unfinished: { ...savedTurn, id: "e".repeat(32), state: "created" } };
    }
    for (const [stage, state, branch] of [["plan", "planned", "reuse"], ["evidence", "ready", "reuse"], ["answer", "completed", "reuse"], ["stop", "stopped", "reuse"]]) {
      if (path.endsWith(`/${stage}`)) {
        const turns = (data.turns as typeof savedTurn[]).map((t, i, all) => i === all.length - 1 ? { ...t, state, branch, answer: state === "completed" ? "A saved follow-up answer." : null } : t);
        data = { ...data, turns, unfinished: state === "completed" || state === "stopped" ? null : turns.at(-1) };
      }
    }
    if (method === "DELETE") return new Response(null, { status: 204 });
    return Response.json(data);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
function mount(path = `/conversations/${id}`) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/conversations" element={<ConversationsPage />} />
    <Route path="/conversations/:id" element={<ConversationPage />} />
    <Route path="/start" element={<SavedQuestion available params={new URLSearchParams("q=First+question")} />} />
  </Routes></MemoryRouter></QueryClientProvider>);
  return cache;
}
it("restores saved answers while AI is disabled without paid POSTs", async () => {
  enabled = false; mount();
  await screen.findByText(savedTurn.answer);
  await screen.findByText("AI answers are disabled. Saved history remains available.");
  expect(requests.every(r => r.method === "GET")).toBe(true);
  expect(screen.getByRole("link", { name: /Original · Version 7/ }).getAttribute("href")).toContain(`returnTo=%2Fconversations%2F${id}`);
});
it("requires new consent and runs each follow-up stage once", async () => {
  mount(); await screen.findByText(savedTurn.answer);
  const send = screen.getByRole("button", { name: "Send question" }) as HTMLButtonElement;
  expect(send.disabled).toBe(true);
  fireEvent.change(screen.getByRole("textbox", { name: "Question" }), { target: { value: "Explain that again." } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Allow this question and its context to be sent to OpenAI" }));
  await waitFor(() => expect(send.disabled).toBe(false)); fireEvent.click(send);
  await screen.findByText("A saved follow-up answer.");
  expect(requests.filter(r => r.method === "POST").map(r => r.path.split("/").at(-1))).toEqual(["turns", "plan", "evidence", "answer"]);
  expect((screen.getByRole("checkbox", { name: "Allow this question and its context to be sent to OpenAI" }) as HTMLInputElement).checked).toBe(false);
});
it("reconnect shows an unfinished turn without resuming it and allows stop", async () => {
  data = { ...data, unfinished: { ...savedTurn, state: "answering" } };
  mount(); await screen.findByRole("button", { name: "Stop unfinished question" });
  expect(requests.every(r => r.method === "GET")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Stop unfinished question" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: "Stop unfinished question" })).toBeNull());
  expect(requests.filter(r => r.method === "POST")).toHaveLength(1);
});
it("hides another account's cached body immediately after session changes", async () => {
  mount(); await screen.findByText(savedTurn.answer);
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
  setAccessToken("different-owner");
  await waitFor(() => expect(screen.queryByText(savedTurn.answer)).toBeNull());
});
it("lists saved conversations using GET and deletes the selected conversation", async () => {
  mount(); await screen.findByText(savedTurn.answer);
  fireEvent.click(screen.getByRole("button", { name: "Delete conversation" }));
  await screen.findByRole("heading", { name: "Saved conversations" });
  expect(requests.filter(r => r.method === "DELETE")).toHaveLength(1);
  expect(requests.filter(r => r.method === "POST")).toHaveLength(0);
});
it("creates and executes a saved first question only after explicit consent", async () => {
  mount("/start");
  expect(requests).toHaveLength(0);
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Ask from my records" }));
  await screen.findByRole("heading", { name: "My saved chat" });
  expect(requests.filter(r => r.method === "POST").map(r => r.path.split("/").at(-1))).toEqual(["answer-conversations", "turns", "plan", "evidence", "answer"]);
});

it("keeps the stopped snapshot when aborting an in-flight answer", async () => {
  const original = vi.mocked(fetch).getMockImplementation()!;
  let answerStarted = false;
  let stopSent = false;
  let readsAfterAbort = 0;
  vi.stubGlobal("fetch", vi.fn(async (path: string, init: RequestInit = {}) => {
    if (path.endsWith("/answer")) {
      answerStarted = true;
      return new Promise<Response>((_, reject) => init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));
    }
    if (path.endsWith("/stop")) {
      stopSent = true;
      // Let the answer abort handler/finally run before stop returns, as in a real browser.
      await new Promise(resolve => setTimeout(resolve, 20));
    }
    if (stopSent && path === `/api/answer-conversations/${id}` && (!init.method || init.method === "GET")) readsAfterAbort++;
    return original(path, init);
  }));
  mount(); await screen.findByText(savedTurn.answer);
  fireEvent.change(screen.getByRole("textbox", { name: "Question" }), { target: { value: "Slow answer" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Allow this question and its context to be sent to OpenAI" }));
  fireEvent.click(screen.getByRole("button", { name: "Send question" }));
  await waitFor(() => expect(answerStarted).toBe(true));
  fireEvent.click(screen.getByRole("button", { name: "Stop unfinished question" }));
  await screen.findByText(/Stopped\. A request already sent/);
  await waitFor(() => expect(screen.queryByRole("button", { name: "Stop unfinished question" })).toBeNull());
  expect(readsAfterAbort).toBe(0);
});

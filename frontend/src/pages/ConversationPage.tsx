import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import { changeConversation, claimTurn, conversationStage, deleteConversation, fetchConversation, runTurn, type Conversation, type Turn } from "../api/answerConversations";
import { fetchAnswerStatus } from "../api/answers";
import { getAccessToken, useAccessToken } from "../utils/session";

export default function ConversationPage() {
  const { id = "" } = useParams();
  const token = useAccessToken();
  return <ConversationView key={`${token}:${id}`} id={id} token={token} />;
}
function ConversationView({ id, token }: { id: string; token: string | null }) {
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [consent, setConsent] = useState(false);
  const [fresh, setFresh] = useState(false);
  const [base, setBase] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [before, setBefore] = useState<number>();
  const controller = useRef<AbortController | null>(null);
  const active = useRef<{ id: string; turn: Turn } | null>(null);
  const pending = useRef(false);
  const key = ["conversation", token, id, before];
  const query = useQuery({ queryKey: key, queryFn: ({ signal }) => fetchConversation(id, signal, before), enabled: !!token, retry: false, gcTime: 0 });
  const status = useQuery({ queryKey: ["answer-status", token], queryFn: ({ signal }) => fetchAnswerStatus(signal), retry: false, gcTime: 0 });
  const value = query.data;
  useEffect(() => () => {
    controller.current?.abort();
    if (active.current && getAccessToken() === token) void conversationStage(active.current.id, active.current.turn, "stop").catch(() => {});
  }, [token]);
  const update = (data: Conversation) => {
    if (getAccessToken() !== token) return;
    cache.setQueryData(key, data);
    const turn = data.unfinished;
    active.current = turn ? { id: data.id, turn } : null;
  };
  const stop = async () => {
    controller.current?.abort();
    const current = active.current ?? (value?.unfinished ? { id: value.id, turn: value.unfinished } : null);
    if (current) {
      const stopped = await conversationStage(current.id, current.turn, "stop");
      await cache.cancelQueries({ queryKey: key, exact: true });
      update(stopped);
    }
  };
  const run = async () => {
    if (!value || pending.current) return;
    pending.current = true; setBusy(true); setError("");
    const control = new AbortController(); controller.current = control;
    const timer = window.setTimeout(() => { control.abort(); void stop().catch(() => {}); }, 120000);
    try {
      const claimed = await claimTurn(id, { q, request_id: crypto.randomUUID().replaceAll("-", ""),
        expected_revision: value.revision, context_mode: fresh ? "fresh" : "continue", base_turn_id: fresh ? undefined : base,
        confirm_external_ai: true }, control.signal);
      update(claimed); setQ("");
      await runTurn(claimed, control.signal, update);
      setBase(undefined); setFresh(false);
    } catch (e) { if (getAccessToken() === token) setError((e as Error).name === "AbortError" ? "Stopped. A request already sent may have been charged." : (e as Error).message); }
    finally {
      window.clearTimeout(timer);
      pending.current = false;
      if (getAccessToken() === token) {
        setBusy(false); setConsent(false);
        // Stop owns the terminal snapshot; an abort refresh can overwrite it with pre-stop state.
        if (!control.signal.aborted) void query.refetch();
      }
    }
  };
  const act = async (action: "close" | "reopen" | "delete" | "stop" | "interrupt") => {
    if (!value) return;
    try {
      setError("");
      if (action === "delete") { await deleteConversation(id); navigate("/conversations"); return; }
      if (action === "stop") { await stop(); return; }
      if (action === "interrupt" && value.unfinished) update(await conversationStage(id, value.unfinished, "interrupt"));
      if (action === "close" || action === "reopen") update(await changeConversation(value, action));
    } catch (e) { setError((e as Error).message); }
  };
  return <div className="saved-conversation"><Link to="/conversations">Back to conversations</Link>
    {query.isLoading && <p role="status">Loading conversation...</p>}
    {(error || query.error) && <p role="alert">{error || query.error?.message}</p>}
    <button onClick={() => { setConsent(false); void query.refetch(); void status.refetch(); }}>Refresh saved state</button>
    {value && !query.error && <><header className="page-header"><div><h2>{value.title}</h2><p>{value.state} · Saved until you delete it. Closing or logging out preserves this history.</p></div></header>
      <p className="help-text">Scope: {String(value.filters.source ?? "all sources")} · {String(value.filters.entry_type ?? "all record types")} · {String(value.filters.date_from ?? "any start date")} to {String(value.filters.date_to ?? "any end date")} (by {value.filters.date_field === "event_at" ? "source date" : "added date"}). To change filters, <Link to="/search">start another conversation</Link>.</p>
      <div className="actions"><button disabled={busy || !!value.unfinished} onClick={() => void act(value.state === "closed" ? "reopen" : "close")}>{value.state === "closed" ? "Reopen conversation" : "Close conversation"}</button>
        <button onClick={() => void act("delete")}>Delete conversation</button></div>
      {value.next_before && <button onClick={() => setBefore(value.next_before!)}>Earlier turns</button>}
      {before && <button onClick={() => setBefore(undefined)}>Latest turns</button>}
      {value.turns.map(t => <article className="panel" key={t.id}>
        <h3>Question {t.seq}</h3><p className="entry-content">{t.q}</p>
        <p>{t.state}{t.outcome ? ` · ${t.outcome}` : ""}{t.answer_status ? ` · ${t.answer_status}` : ""}</p>
        {t.base_turn_id && <p className="help-text">Follow-up to a selected saved answer</p>}
        {t.availability !== "available" && <p role="status">Source {t.availability}. This context cannot be sent to AI again. Use a new independent context.</p>}
        {t.answer && <p className="entry-content">{t.answer}</p>}
        {t.error_code && <p role="status">{t.error_code}. No automatic retry.</p>}
        {!!t.citations.length && <ul>{t.citations.map((c, i) => <li key={i}><Link to={`/citations?${new URLSearchParams({ version_id: String(c.version_id), field: c.field, start: String(c.start), end: String(c.end), passage_hash: c.passage_hash, returnTo: `/conversations/${id}` })}`}>Original · Version {c.version_id} · Characters {c.start + 1}–{c.end}</Link></li>)}</ul>}
        {!!t.usage.length && <p className="help-text">AI usage: {t.usage.map(u => `${u.purpose}: ${u.status}`).join(", ")}. Stopping cannot reverse sent requests or charges.</p>}
        <details><summary>Context sent</summary>{Object.entries(t.context_summary).filter(([, v]) => v && typeof v === "object").map(([name, raw]) => {
          const context = raw as { history_ids?: string[]; omitted?: string[]; selected?: number; omissions?: string[] };
          return <p className="help-text" key={name}>{name === "plan" ? "Question interpretation" : name === "answer" ? "Answer" : name === "search" ? "Search" : "Source selection"}: {context.history_ids?.length ?? 0} earlier turns included, {context.omitted?.length ?? 0} left out for length.{context.selected !== undefined ? ` ${context.selected} original passages selected; ${context.omissions?.length ?? 0} matches omitted for count or size limits.` : ""}</p>;
        })}</details>
        {t.outcome === "answer" && t.state === "completed" && t.availability === "available" && <button disabled={busy || !!value.unfinished} onClick={() => { setBase(t.id); setFresh(false); setConsent(false); }}>Follow up on this answer</button>}
      </article>)}
      {value.unfinished && <section className="panel"><p role="status">Unfinished question · {value.unfinished.state}. Opening this chat does not resume it. A request may have been charged without a saved answer.</p>
        <button onClick={() => void act("stop")}>Stop unfinished question</button>
        <button onClick={() => void act("interrupt")}>Clear expired question</button></section>}
      {!before && value.state === "active" && <section className="panel"><h3>Ask a follow-up</h3>
        {base && <p>Following up on a selected answer. <button onClick={() => setBase(undefined)}>Clear selection</button></p>}
        <label>Question<textarea maxLength={256} value={q} disabled={busy} onChange={e => { setQ(e.target.value); setConsent(false); }} /></label>
        <label><input type="checkbox" checked={fresh} disabled={busy} onChange={e => { setFresh(e.target.checked); setBase(undefined); setConsent(false); }} />Start an independent context in this conversation</label>
        <p className="help-text">Each question is saved. OpenAI receives the question, limited eligible dialogue and up to five allowed originals. At most three AI calls, reservation up to USD 0.011817. Opening history is free.</p>
        <label><input type="checkbox" checked={consent} disabled={busy || !!value.unfinished} onChange={e => setConsent(e.target.checked)} />Allow this question and its context to be sent to OpenAI</label>
        {!status.data?.enabled && <p role="status">AI answers are disabled. Saved history remains available.</p>}
        <button className="primary" disabled={busy || !!value.unfinished || !q.trim() || !consent || !status.data?.enabled} onClick={() => void run()}>Send question</button>
      </section>}
    </>}
  </div>;
}

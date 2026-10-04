import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useSearchParams } from "react-router";
import { historyRequest } from "../api/history";
import { deleteEntry, fetchEntry } from "../api/entries";
import type { components } from "../api/generated/schema";
import { entryTarget, listTarget, resolveEntryContext, validPage } from "../utils/entryNavigation";
import { formatEntryDate } from "../utils/entries";
import { invalidateRecordViews } from "../utils/recordCache";
import { sessionTarget } from "../utils/codexSessions";
import CodexReader from "../components/CodexReader";
import EntryHistory from "../components/EntryHistory";

type Turn = components["schemas"]["TurnSummary"];
function SessionTurn({ turn, initiallyOpen, origin, sessionURL }: { turn: Turn; initiallyOpen: boolean; origin: string; sessionURL: string }) {
  const [open, setOpen] = useState(initiallyOpen);
  const [confirm, setConfirm] = useState(false);
  const cache = useQueryClient();
  const entry = useQuery({ queryKey: ["entry", String(turn.id)], queryFn: () => fetchEntry(String(turn.id)), enabled: open });
  const remove = useMutation({ mutationFn: () => deleteEntry(String(turn.id)), onSuccess: async () => {
    cache.removeQueries({ queryKey: ["entry", String(turn.id)], exact: true });
    cache.removeQueries({ queryKey: ["entry-versions", turn.id] });
    await invalidateRecordViews(cache);
    await Promise.all(["suppressed", "purges"].map(key => cache.invalidateQueries({ queryKey: [key] })));
  } });
  const context = resolveEntryContext(`?${new URLSearchParams({ returnTo: origin })}`);
  const detail = `${entryTarget(turn.id, context)}&${new URLSearchParams({ sessionReturn: sessionURL })}`;
  return <article className="panel session-turn" id={`turn-${turn.id}`}>
    <button className="turn-toggle" aria-expanded={open} onClick={() => setOpen(!open)}><span>{turn.title}</span><span>{open ? "Collapse turn" : "Read turn"}</span></button>
    <p className="record-date">Source/event date: {formatEntryDate(turn.event_at)}</p>
    {open && <>
      {entry.isLoading && <p role="status">Loading turn...</p>}
      {entry.error && <><p role="alert">{entry.error.message}</p><button onClick={() => void entry.refetch()}>Retry turn</button></>}
      {entry.data && <>
        <CodexReader entry={entry.data} />
        <div className="actions"><Link to={detail}>Open record and provenance</Link><button className="danger" onClick={() => setConfirm(true)}>Delete turn</button></div>
        {confirm && <div className="delete-confirm"><p>Delete this turn and all versions? It will be blocked from reimport.</p><button disabled={remove.isPending} className="danger" onClick={() => remove.mutate()}>Confirm delete</button><button disabled={remove.isPending} onClick={() => { setConfirm(false); remove.reset(); }}>Cancel</button>{remove.error && <p role="alert">{remove.error.message}</p>}</div>}
        <EntryHistory entry={entry.data} />
      </>}
    </>}
  </article>;
}

export default function CodexSessionPage() {
  const [params, setParams] = useSearchParams();
  const token = localStorage.getItem("access_token");
  const scope = params.get("scope") ?? ""; const thread = params.get("thread") ?? "";
  const focus = params.get("focus"); const offset = Number(params.get("offset") ?? 0);
  const context = resolveEntryContext(`?${params}`); const origin = listTarget(context);
  const valid = Boolean(scope && scope.length <= 255 && thread && thread.length <= 1024 && validPage(params)
    && (!focus || (/^[1-9]\d*$/.test(focus) && Number.isSafeInteger(Number(focus)))));
  const query = useQuery({ queryKey: ["codex-session", scope, thread, offset, focus],
    queryFn: () => historyRequest<components["schemas"]["SessionTurnsResponse"]>(`/codex-sessions/turns?${new URLSearchParams({ scope, thread_id: thread, limit: "20", offset: String(offset), ...(focus ? { focus_entry_id: focus } : {}) })}`),
    enabled: Boolean(token && valid) });
  const focusReady = Boolean(query.data && !query.data.focus_missing);
  const focusedPage = query.data?.offset;
  useEffect(() => {
    if (focus && focusReady) document.getElementById(`turn-${focus}`)?.scrollIntoView?.({ block: "start" });
  }, [focus, focusReady, focusedPage]);
  if (!token) return <Navigate to="/login" replace />;
  function page(value: number) { const next = new URLSearchParams(params); next.delete("focus"); if (value) next.set("offset", String(value)); else next.delete("offset"); setParams(next); }
  const data = query.data;
  return <>
    <Link className="back-link" to={origin}>← {context.pathname === "/search" ? "Back to search" : "Back to entries"}</Link>
    {!valid && <p role="alert">Invalid session address or page.</p>}
    {query.isLoading && <p role="status">Loading session...</p>}
    {query.error && <><p role="alert">{query.error.message}</p><button onClick={() => void query.refetch()}>Retry session</button></>}
    {data && <>
      <header className="panel session-header"><span className="badge source">Codex session</span><h2>{data.session.title}</h2>
        <p>{data.total} retained turns · Page {Math.floor(data.offset / 20) + 1}</p>
        <p className="record-date">Source period: {formatEntryDate(data.session.start_at)} – {formatEntryDate(data.session.end_at)}</p>
        <p className="help-text">Stored turns may be a subset of the original session. See Sources for collection coverage.</p>
        {data.session.order_unknown && <p className="review-notice">Original turn order unverified. Known source dates and record IDs provide the displayed order.</p>}
        {data.session.archived && <p>Read from archived history.</p>}
        {data.session.forked_from_id && <p>Forked from: {data.session.fork_available
          ? <Link to={sessionTarget({ source_scope: scope, thread_id: data.session.forked_from_id }, context)}>Open original session</Link>
          : data.session.forked_from_id}</p>}
        {data.session.metadata_conflict && <p className="review-notice">Conflicting archive or fork metadata is retained.</p>}
        {data.focus_missing && <p role="status">The requested turn is unavailable in this session. Showing retained records.</p>}
      </header>
      {data.items.map((turn, index) => <SessionTurn key={`${scope}:${thread}:${data.offset}:${turn.id}`} turn={turn} initiallyOpen={turn.id === Number(focus) || (!focus && index === 0) || (data.focus_missing && index === 0)} origin={origin} sessionURL={`/sessions/codex?${params}`} />)}
      <div className="actions pagination"><button disabled={query.isFetching || data.offset === 0} onClick={() => page(Math.max(0, data.offset - 20))}>Previous turns</button><button disabled={query.isFetching || data.offset + 20 >= data.total} onClick={() => page(data.offset + 20)}>Next turns</button></div>
    </>}
  </>;
}

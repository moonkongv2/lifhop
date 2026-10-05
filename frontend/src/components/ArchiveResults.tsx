import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { historyRequest } from "../api/history";
import type { components } from "../api/generated/schema";
import { entryTarget, listContext, validPage } from "../utils/entryNavigation";
import { sessionTarget } from "../utils/codexSessions";
import { formatEntryDate, sourceLabels } from "../utils/entries";
import { repositoryLink } from "../utils/githubRepositories";

export default function ArchiveResults() {
  const [params, setParams] = useSearchParams();
  const offset = Number(params.get("offset") ?? 0);
  const valid = validPage(params);
  const context = listContext("/entries", params);
  const query = useQuery({ queryKey: ["archive", offset],
    queryFn: () => historyRequest<components["schemas"]["ArchiveResponse"]>(`/archive?limit=20${offset ? `&offset=${offset}` : ""}`), enabled: valid });
  const data = query.data;
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total) {
      const next = new URLSearchParams(); const last = Math.max(0, Math.ceil(data.total / 20) - 1) * 20;
      if (last) next.set("offset", String(last));
      setParams(next, { replace: true });
    }
  }, [data, offset, setParams]);
  function page(value: number) { setParams(value ? new URLSearchParams({ offset: String(value) }) : new URLSearchParams()); }
  return <section aria-label="Recent entries">
    {!valid && <><p role="alert">Invalid page value. Please reset the page.</p><button onClick={() => page(0)}>Reset page</button></>}
    {query.isLoading && valid && <p role="status">Loading...</p>}
    {query.error && <><p role="alert">{query.error.message}</p><button onClick={() => void query.refetch()}>Retry</button></>}
    {data && valid && <>
      <div className="records-toolbar"><p>{data.total} archive {data.total === 1 ? "item" : "items"} · Page {Math.floor(offset / 20) + 1}</p><span>Most recently added · Codex sessions · GitHub repositories</span></div>
      {!data.items.length && <div className="panel empty-state"><p>No entries yet.</p><span>Create a note or import your first records.</span></div>}
      <div className="records-grid">{data.items.map(row => row.repository ? <article className="panel record-card" key={`repository:${row.repository.source_scope}`}>
        <span className="badge source">GitHub repository</span>
        <Link to={repositoryLink(row.repository.source_scope,context)}><h3>{row.repository.repository ?? row.repository.source_scope}</h3></Link>
        <p>{row.repository.commit_count} retained commits · {row.repository.document_count} document paths · {row.repository.snapshot_count} snapshots</p>
        {!!row.repository.unclassified_count && <p>{row.repository.unclassified_count} unclassified records</p>}
        <p className="record-date">Source period: {formatEntryDate(row.repository.start_at)} – {formatEntryDate(row.repository.end_at)}</p>
        {!!row.repository.unknown_date_count && <p className="help-text">{row.repository.unknown_date_count} records have an unknown source date.</p>}
        {(row.repository.partial || row.repository.review_required) && <span className="badge">Partial evidence or version review</span>}
        <p className="help-text">Counts cover retained records. Collection coverage is available in Sources.</p>
      </article> : row.session ? <article className="panel record-card" key={`session:${JSON.stringify([row.session.source_scope, row.session.thread_id])}`}>
        <span className="badge source">Codex session</span>
        <Link to={sessionTarget(row.session, context)}><h3>{row.session.title}</h3></Link>
        {row.session.preview_text && <p className="entry-content session-preview">{row.session.preview_text}</p>}
        <p>{row.session.turn_count} retained turns</p>
        <p className="record-date">Source period: {formatEntryDate(row.session.start_at)} – {formatEntryDate(row.session.end_at)}</p>
        {row.session.order_unknown && <p className="help-text">Original turn order unverified.</p>}
        {(row.session.partial || row.session.review_required) && <span className="badge">Partial evidence or version review</span>}
        <p className="help-text">Counts cover stored turns. Collection coverage is available in Sources.</p>
      </article> : row.entry ? <article className="panel record-card" key={row.entry.id}>
        <div className="badges"><span className="badge source">{sourceLabels[row.entry.source]}</span><span className="badge">{row.entry.type}</span></div>
        <Link to={entryTarget(row.entry.id, context)}><h3>{row.entry.title}</h3></Link>
        {row.entry.source_state === "deleted" && <span className="badge">Deleted at source</span>}
        {row.entry.provider === "codex" && <p className="help-text">Session classification unavailable for this record.</p>}
        {row.entry.provider === "github" && <p className="help-text">Repository classification unavailable for this record.</p>}
        <p className="entry-content">{row.entry.content ?? "No content"}</p>
        <p className="record-date">Added: {formatEntryDate(row.entry.created_at)} · Source/event date: {formatEntryDate(row.entry.event_at)} (Asia/Seoul)</p>
      </article> : null)}</div>
      <div className="actions pagination"><button disabled={query.isFetching || offset === 0} onClick={() => page(Math.max(0, offset - 20))}>Previous page</button><button disabled={query.isFetching || offset + 20 >= data.total} onClick={() => page(offset + 20)}>Next page</button></div>
    </>}
  </section>;
}

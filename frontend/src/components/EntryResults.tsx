import { useEffect } from "react";
import { Link, useSearchParams } from "react-router";
import useEntrySearch from "../hooks/useEntrySearch";
import { entryTarget, listContext } from "../utils/entryNavigation";
import { formatEntryDate, sourceLabels } from "../utils/entries";
import Icon from "./Icon";
import { sessionTarget } from "../utils/codexSessions";
import { repositoryLink } from "../utils/githubRepositories";

export default function EntryResults({ searching }: { searching: boolean }) {
  const [rawParams, setParams] = useSearchParams();
  const context = listContext(searching ? "/search" : "/entries", rawParams);
  const serialized = context.search;
  const params = new URLSearchParams(serialized);
  const { data, isLoading, isFetching, error, refetch, offset, validOffset } = useEntrySearch(params);
  useEffect(() => {
    if (data && validOffset && offset > 0 && offset >= data.total) {
      const next = new URLSearchParams(serialized);
      const last = Math.max(0, Math.ceil(data.total / 20) - 1) * 20;
      if (last === 0) next.delete("offset"); else next.set("offset", String(last));
      setParams(next, { replace: true });
    }
  }, [data, validOffset, offset, serialized, setParams]);
  function page(nextOffset: number) {
    const next = new URLSearchParams(serialized);
    if (nextOffset === 0) next.delete("offset"); else next.set("offset", String(nextOffset));
    setParams(next);
  }
  return <section aria-label={searching ? "Search results" : "Recent entries"}>
    {!validOffset && <><p role="alert">Invalid page value. Please reset the page.</p><button onClick={() => page(0)}>Reset page</button></>}
    {isLoading && validOffset && <p role="status">Loading...</p>}
    {error && <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>Retry</button></>}
    {data && validOffset && <>
      <div className="records-toolbar"><p>{data.total} {data.total === 1 ? "entry" : "entries"} · Page {Math.floor(offset / 20) + 1}</p><span>{params.get("q") ? "Title matches first" : "Most recently added"}</span></div>
      {data.items.length === 0 && <div className="panel empty-state"><Icon name="archive" /><p>{searching ? "No entries match your search." : "No entries yet."}</p><span>{searching ? "Try another phrase or reset your filters." : "Create a note or import your first records."}</span></div>}
      <div className="records-grid">{data.items.map((entry) => <article className="panel record-card" key={entry.id}>
        <div className="badges"><span className="badge source"><Icon name="note" />{sourceLabels[entry.source ?? "unknown"]}</span><span className="badge">{entry.type}</span></div>
        <Link to={entry.session_ref ? sessionTarget(entry.session_ref, context, entry.id) : entryTarget(entry.id, context)}><h3>{entry.title}</h3></Link>
        {entry.matched_in_commentary_only && <span className="badge">Matched in work commentary</span>}
        {entry.source_state === "deleted" && <span className="badge">Deleted at source</span>}
        {entry.repository_ref && <p className="help-text">{entry.repository_ref.repository ?? entry.repository_ref.source_scope} · {entry.repository_ref.kind}<br />
          <Link to={repositoryLink(entry.repository_ref.source_scope,context)}>Browse repository</Link></p>}
        <p className="entry-content">{entry.preview_text ?? entry.content ?? "No content"}</p>
        <p className="record-date">Added: {formatEntryDate(entry.created_at)} · Source/event date: {formatEntryDate(entry.event_at)} (Asia/Seoul)</p>
      </article>)}</div>
      <div className="actions pagination">
        <button disabled={isFetching || offset === 0} onClick={() => page(Math.max(0, offset - 20))}>Previous page</button>
        <button disabled={isFetching || offset + 20 >= data.total} onClick={() => page(offset + 20)}>Next page</button>
      </div>
    </>}
  </section>;
}

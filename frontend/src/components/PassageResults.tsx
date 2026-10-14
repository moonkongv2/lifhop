import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { fetchPassages, fetchPassageSnapshots } from "../api/passages";
import type { Passage } from "../api/passages";
import { entryTarget, listContext, listTarget, validPage } from "../utils/entryNavigation";
import { formatEntryDate, sourceLabels } from "../utils/entries";
import { sessionTarget } from "../utils/codexSessions";
import { repositoryLink } from "../utils/githubRepositories";
import SelectedAnswer from "./SelectedAnswer";

function passageTarget(id: number, params: URLSearchParams) {
  return `/passages/${id}?${new URLSearchParams({ returnTo: listTarget(listContext("/search", params)) })}`;
}

function SnapshotLinks({ passage, params }: { passage: Passage; params: URLSearchParams }) {
  const [expanded, setExpanded] = useState(false);
  const [offset, setOffset] = useState(0);
  const serialized = params.toString();
  const { data, error, isFetching } = useQuery({ queryKey: ["passage-snapshots", passage.id, serialized, offset],
    queryFn: ({ signal }) => fetchPassageSnapshots(passage.id, new URLSearchParams(serialized), offset, signal), enabled: expanded, retry: false });
  if (passage.alias_total <= 1) return null;
  return <div className="passage-snapshots"><button aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? "Hide locations" : `View ${passage.alias_total} retained locations`}</button>
    {expanded && <>{isFetching && <p role="status">Loading locations...</p>}{error && <p role="alert">{error.message}</p>}
      {data && <><ul>{data.items.map(item => <li key={item.id}><Link to={passageTarget(item.id, params)}>Record {item.entry_id} · {formatEntryDate(item.event_at)}</Link></li>)}</ul>
        <div className="actions"><button disabled={offset === 0 || isFetching} onClick={() => setOffset(Math.max(0, offset-20))}>Previous locations</button><button disabled={offset+20 >= data.total || isFetching} onClick={() => setOffset(offset+20)}>Next locations</button></div></>}
    </>}
  </div>;
}

export default function PassageResults({ params }: { params: URLSearchParams }) {
  const [, setParams] = useSearchParams();
  const [selected, setSelected] = useState<number[]>([]);
  const serialized = params.toString();
  const offset = Number(params.get("offset") ?? 0);
  const valid = validPage(params);
  const context = listContext("/search", params);
  const { data, error, isLoading, isFetching, refetch } = useQuery({ queryKey: ["passages", serialized],
    queryFn: ({ signal }) => fetchPassages(new URLSearchParams(serialized), signal), enabled: valid, retry: false });
  function page(value: number) {
    const next = new URLSearchParams(serialized);
    if (value) next.set("offset", String(value)); else next.delete("offset");
    setParams(next);
  }
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total) {
      const next = new URLSearchParams(serialized);
      const last = Math.max(0, Math.ceil(data.total/20)-1)*20;
      if (last) next.set("offset", String(last)); else next.delete("offset");
      setParams(next, { replace: true });
    }
  }, [data, offset, serialized, setParams]);
  return <section aria-label="Passage search results">
    {!valid && <><p role="alert">Invalid page value.</p><button onClick={() => page(0)}>Reset page</button></>}
    {isLoading && <p role="status">Finding passages...</p>}
    {error && <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>Retry</button></>}
    {data && <>
      {Object.entries(data.coverage).some(([status, count]) => status !== "ready" && count > 0) && <p role="status" className="panel">Index coverage: {Object.entries(data.coverage).map(([status, count]) => `${count} ${status}`).join(" · ")}. Some records are not fully searchable in this mode.</p>}
      <div className="records-toolbar"><p>{data.total} {data.total === 1 ? "passage" : "passages"} · Page {Math.floor(offset/20)+1}</p><span>Related words · Current retained versions</span></div>
      {data.items.length === 0 && <div className="panel empty-state"><h3>No matching passages</h3><p>Try words used in the source, another language, or Exact phrase search.</p></div>}
      <div className="records-grid">{data.items.map(p => <article className="panel record-card" key={p.id}>
        <div className="badges"><span className="badge source">{sourceLabels[p.source as keyof typeof sourceLabels] ?? p.source}</span><span className="badge">{p.field === "title" ? "Title match" : "Original passage"}</span>{p.work_only && <span className="badge">Work details</span>}{p.source_state === "deleted" && <span className="badge">Deleted at source</span>}{p.index_status === "partial" && <span className="badge">Partial index</span>}</div>
        {p.completeness !== "complete" && <span className="badge">Incomplete source</span>}
        <h3>{p.title}</h3><p className="entry-content">{p.text}</p>
        {p.field === "content" && !p.work_only && p.source_state !== "deleted" && <label className="work-search-option"><input type="checkbox"
          checked={selected.includes(p.id)} disabled={!selected.includes(p.id) && selected.length >= 5}
          onChange={e => setSelected(current => e.target.checked ? [...current, p.id] : current.filter(id => id !== p.id))} />Use this passage for an answer</label>}
        <p className="help-text">{p.repository_ref?.repository ?? p.session_ref?.thread_id ?? ""}{p.repository_ref?.path ? ` · ${p.repository_ref.path}` : ""}</p>
        <p className="record-date">Source/event date: {formatEntryDate(p.event_at)} · Added: {formatEntryDate(p.created_at)}<br />Version {p.version_id} · {p.snapshot_count} retained {p.snapshot_count === 1 ? "snapshot" : "snapshots"}</p>
        <div className="actions"><Link to={passageTarget(p.id, params)}>View passage</Link><Link to={p.session_ref ? sessionTarget(p.session_ref, context, p.entry_id) : entryTarget(p.entry_id, context)}>Open record</Link>{p.repository_ref && <Link to={repositoryLink(p.repository_ref.source_scope, context)}>Browse repository</Link>}</div>
        <SnapshotLinks passage={p} params={params} />
      </article>)}</div>
      {!error && <><p className="help-text">Answer requests use only selected content passages. Source or record AI exclusions are checked again before sending.</p>
        <SelectedAnswer key={selected.join(",")} question={params.get("q") ?? ""} selected={selected} params={params} kind="passage" /></>}
      <div className="actions pagination"><button disabled={offset === 0 || isFetching} onClick={() => page(Math.max(0, offset-20))}>Previous page</button><button disabled={offset+20 >= data.total || isFetching} onClick={() => page(offset+20)}>Next page</button></div>
    </>}
  </section>;
}

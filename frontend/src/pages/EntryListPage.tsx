import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useSearchParams } from "react-router";
import { fetchEntrySearch } from "../api/entries";
import { formatEntryDate, sourceLabels } from "../utils/entries";

function SearchForm({ params, onApply }: { params: URLSearchParams; onApply: (params: URLSearchParams) => void }) {
  const [q, setQ] = useState(params.get("q") ?? "");
  const [source, setSource] = useState(params.get("source") ?? "");
  const [sourceState, setSourceState] = useState(params.get("source_state") ?? "");
  const [type, setType] = useState(params.get("type") ?? "");
  const [dateField, setDateField] = useState(params.get("date_field") ?? "created_at");
  const [from, setFrom] = useState(params.get("date_from") ?? "");
  const [to, setTo] = useState(params.get("date_to") ?? "");
  const [validation, setValidation] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (from && to && from > to) { setValidation("Start date must be on or before end date."); return; }
    setValidation("");
    const next = new URLSearchParams();
    for (const [key, value] of Object.entries({ q: q.trim(), source, source_state: sourceState, type, date_field: dateField, date_from: from, date_to: to })) {
      if (value && !(key === "date_field" && value === "created_at")) next.set(key, value);
    }
    onApply(next);
  }

  return (
    <form onSubmit={submit}>
      <label htmlFor="search-q">Search query</label>
      <input id="search-q" value={q} maxLength={256} onChange={(event) => setQ(event.target.value)} placeholder="Search titles and content for phrases, names, numbers, or code" />
      <div className="search-filters">
        <label>Source<select value={source} onChange={(event) => setSource(event.target.value)}>
          <option value="">All sources</option>
          {Object.entries(sourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label>Source status<select value={sourceState} onChange={e => setSourceState(e.target.value)}>
          <option value="">All retained records</option>
          {["available", "deleted", "unavailable", "unknown"].map(value => <option key={value} value={value}>{value}</option>)}
        </select></label>
        <label>Type<select value={type} onChange={(event) => setType(event.target.value)}>
          <option value="">All types</option><option value="NOTE">Note</option><option value="LOG">Log</option>
          <option value="DOCUMENT">Document</option><option value="CONVERSATION">Conversation</option><option value="PROJECT_EVENT">Project event</option>
        </select></label>
        <label>Date field<select value={dateField} onChange={(event) => setDateField(event.target.value)}>
          <option value="created_at">Added</option><option value="event_at">Source/event date</option>
        </select></label>
        <label>Start date<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
        <label>End date<input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label>
      </div>
      <p>Date ranges use Asia/Seoul and include the end date. Records without a source/event date are excluded when filtering by that date.</p>
      <div className="actions"><button type="submit">Search</button><button type="button" onClick={() => onApply(new URLSearchParams())}>Reset</button></div>
      {validation && <p role="alert">{validation}</p>}
    </form>
  );
}

function EntryListPage() {
  const [params, setParams] = useSearchParams();
  const serialized = params.toString();
  const offset = Number(params.get("offset") ?? 0);
  const validOffset = Number.isSafeInteger(offset) && offset >= 0;
  const token = localStorage.getItem("access_token");
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["entries", serialized],
    queryFn: ({ signal }) => fetchEntrySearch(params, signal),
    enabled: Boolean(token && validOffset),
  });
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total) {
      const next = new URLSearchParams(serialized);
      const last = Math.max(0, Math.ceil(data.total / 20) - 1) * 20;
      if (last === 0) next.delete("offset"); else next.set("offset", String(last));
      setParams(next, { replace: true });
    }
  }, [data, offset, serialized, setParams]);

  function page(nextOffset: number) {
    const next = new URLSearchParams(params);
    if (nextOffset === 0) next.delete("offset"); else next.set("offset", String(nextOffset));
    setParams(next);
  }
  if (!token) return <Navigate to="/login" replace />;
  const filtered = ["q", "source", "source_state", "type", "date_from", "date_to"].some((key) => params.get(key));
  return (
    <>
      <h2>Entries</h2>
      <Link to="/entries/new" state={{ entryListSearch: serialized }}>New note</Link>
      <SearchForm key={serialized} params={params} onApply={setParams} />
      {!validOffset && <p role="alert">Invalid page value. Please reset the search.</p>}
      {isLoading && <p role="status">Loading...</p>}
      {error && <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>Retry</button></>}
      {data && <>
        <p>{data.total} {data.total === 1 ? "entry" : "entries"} · Page {Math.floor(offset / 20) + 1}</p>
        {data.items.length === 0 && <p>{filtered ? "No entries match your search." : "No entries yet."}</p>}
        {data.items.map((entry) => <article key={entry.id}>
          <Link to={`/entries/${entry.id}`} state={{ entryListSearch: serialized }}><h3>{entry.title}</h3></Link>
          <p>{sourceLabels[entry.source ?? "unknown"]} · {entry.type} · Source: {entry.source_state ?? "unknown"}</p>
          <p>Added: {formatEntryDate(entry.created_at)} · Source/event date: {formatEntryDate(entry.event_at)} (Asia/Seoul)</p>
          <p className="entry-content">{entry.content ?? "No content"}</p>
        </article>)}
        <div className="actions">
          <button disabled={isFetching || offset === 0} onClick={() => page(Math.max(0, offset - 20))}>Previous page</button>
          <button disabled={isFetching || offset + 20 >= data.total} onClick={() => page(offset + 20)}>Next page</button>
        </div>
      </>}
    </>
  );
}

export default EntryListPage;

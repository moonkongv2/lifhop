import { useState } from "react";
import type { FormEvent } from "react";
import { sourceLabels } from "../utils/entries";
import DateInput from "./DateInput";
import { validDate } from "../utils/dates";
import Icon from "./Icon";

export default function EntrySearchForm({ params, onApply, onDraftChange }: { params: URLSearchParams; onApply: (params: URLSearchParams) => void; onDraftChange?: () => void }) {
  const [q, setQ] = useState(params.get("q") ?? "");
  const [source, setSource] = useState(params.get("source") ?? "");
  const [sourceState, setSourceState] = useState(params.get("source_state") ?? "");
  const [type, setType] = useState(params.get("type") ?? "");
  const [dateField, setDateField] = useState(params.get("date_field") ?? (params.get("mode") === "retrospective" ? "event_at" : "created_at"));
  const [asOf, setAsOf] = useState(params.get("as_of") ?? "");
  const [from, setFrom] = useState(params.get("date_from") ?? "");
  const [to, setTo] = useState(params.get("date_to") ?? "");
  const [validation, setValidation] = useState("");
  const [includeWork, setIncludeWork] = useState(params.get("include_work_commentary") === "true");
  const [mode, setMode] = useState(["passages", "semantic", "answer", "retrospective", "historical"].includes(params.get("mode") ?? "") ? params.get("mode")! : "exact");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!["exact", "retrospective"].includes(mode) && !q.trim()) { setValidation("Enter a query to search passages."); return; }
    if (mode === "historical") {
      if (!validDate(asOf) || asOf === "9999-12-31") { setValidation("Choose a valid observation cutoff date."); return; }
      setValidation("");
      const next = new URLSearchParams({ mode, q: q.trim(), as_of: asOf });
      if (source) next.set("source", source);
      if (type) next.set("type", type);
      onApply(next); return;
    }
    if ((from && !validDate(from)) || (to && !validDate(to))) { setValidation("Enter a valid date in YYYY-MM-DD format."); return; }
    if (from && to && from > to) { setValidation("Start date must be on or before end date."); return; }
    if (mode === "retrospective" && (!from || !to || Date.parse(to) - Date.parse(from) >= 92 * 86400000)) { setValidation("Choose start and end dates within 92 days."); return; }
    setValidation("");
    const next = new URLSearchParams();
    for (const [key, value] of Object.entries({ q: mode === "retrospective" ? "" : q.trim(), source, source_state: mode === "retrospective" ? "" : sourceState, type, date_field: dateField, date_from: from, date_to: to })) {
      if (value && !(key === "date_field" && value === "created_at" && mode !== "retrospective")) next.set(key, value);
    }
    if (includeWork && !["semantic", "answer", "retrospective", "historical"].includes(mode)) next.set("include_work_commentary", "true");
    if (mode !== "exact") next.set("mode", mode);
    onApply(next);
  }

  const activeFilters = [source, sourceState, type, dateField === "event_at" ? dateField : "", from, to].filter(Boolean).length;
  return (
    <form noValidate className="search-form panel" onSubmit={submit} onChange={onDraftChange}>
      <label>Search mode<select aria-label="Search mode" value={mode} onChange={e => { setMode(e.target.value); if (e.target.value === "retrospective") setDateField("event_at"); }}><option value="exact">Exact phrase</option><option value="passages">Passages</option><option value="semantic">Semantic</option><option value="answer">Answer with sources</option><option value="retrospective">Period retrospective</option><option value="historical">Historical question</option></select></label>
      {mode === "passages" && <p className="help-text">Find related words in original passages. Translation and AI answers are not available yet.</p>}
      {mode === "semantic" && <p className="help-text">Find passages by meaning. Review index availability first, then explicitly approve a paid question request.</p>}
      {mode === "historical" && <p className="help-text">Ask from the latest versions observed by lifhop through a chosen date. Keyword selection is local; this does not reconstruct the external world at that time.</p>}
      {mode === "answer" && <p className="help-text">Ask a question and receive a draft with original sources. Review the filters and transmission consent before running.</p>}
      {mode === "retrospective" ? <p className="help-text">Review up to 92 days by source/event date or added date. The local preview shows sampled originals and coverage before a summary request.</p> : <>
        <label htmlFor="search-q">Search query</label>
        <div className="search-query-row"><input id="search-q" value={q} maxLength={256} onChange={(event) => setQ(event.target.value)} placeholder="Search titles and content for phrases, names, numbers, or code" /><button className="primary" type="submit"><Icon name="search" />{mode === "historical" ? "Review history" : mode === "answer" ? "Review question" : mode === "semantic" ? "Review index" : "Search"}</button></div>
      </>}
      <details className="search-filter-details" open={["retrospective", "historical"].includes(mode) || activeFilters > 0}>
        <summary>Filters{activeFilters > 0 ? ` · ${activeFilters} active` : ""}</summary>
        <div className="search-filters">
          <label>Source<select aria-label="Source" value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="">All sources</option>
            {Object.entries(sourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
          {!["retrospective", "historical"].includes(mode) && <label>Source status<select aria-label="Source status" value={sourceState} onChange={e => setSourceState(e.target.value)}>
            <option value="">{mode !== "exact" ? "Exclude source-deleted records" : "All retained records"}</option>
            {["available", "deleted", "unavailable", "unknown"].map(value => <option key={value} value={value}>{value}</option>)}
          </select></label>}
          <label>Type<select aria-label="Type" value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">All types</option><option value="NOTE">Note</option><option value="LOG">Log</option>
            <option value="DOCUMENT">Document</option><option value="CONVERSATION">Conversation</option><option value="PROJECT_EVENT">Project event</option>
          </select></label>
          {mode === "historical" ? <div><label htmlFor="observed-through">Observed through</label><DateInput id="observed-through" label="Observed through" value={asOf} onChange={value => { setAsOf(value); onDraftChange?.(); }} /></div> : <>
          <label>Date field<select aria-label="Date field" value={dateField} onChange={(event) => setDateField(event.target.value)}>
            <option value="created_at">Added</option><option value="event_at">Source/event date</option>
          </select></label>
          <div><label htmlFor="start-date">Start date</label><DateInput id="start-date" label="Start date" value={from} onChange={value => { setFrom(value); onDraftChange?.(); }} /></div>
          <div><label htmlFor="end-date">End date</label><DateInput id="end-date" label="End date" value={to} onChange={value => { setTo(value); onDraftChange?.(); }} /></div>
          </>}
        </div>
        <p className="help-text">{mode === "historical" ? "The cutoff includes the full day in Asia/Seoul. Observation time is collection time, not the date a decision happened. Versions first collected later are excluded." : "Date ranges use Asia/Seoul and include the end date. Records without a source/event date are excluded when filtering by that date."}</p>
      </details>
      {mode === "retrospective" && <button className="primary" type="submit">Review period</button>}
      {!["semantic", "answer", "retrospective", "historical"].includes(mode) && <label className="work-search-option"><input type="checkbox" checked={includeWork} onChange={event => setIncludeWork(event.target.checked)} />{mode === "passages" ? "Include Codex commands, results, diffs and commentary" : "Include work commentary from Codex"}</label>}
      <button className="search-reset" type="button" onClick={() => onApply(new URLSearchParams())}>Reset</button>
      {validation && <p role="alert">{validation}</p>}
    </form>
  );
}

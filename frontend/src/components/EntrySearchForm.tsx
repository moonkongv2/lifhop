import { useState } from "react";
import type { FormEvent } from "react";
import { sourceLabels } from "../utils/entries";
import { hasSearchConditions } from "../utils/entryNavigation";
import DateInput from "./DateInput";
import { validDate } from "../utils/dates";
import Icon from "./Icon";

export default function EntrySearchForm({ params, onApply, onDraftChange }: { params: URLSearchParams; onApply: (params: URLSearchParams) => void; onDraftChange?: () => void }) {
  const [purpose, setPurpose] = useState(params.get("mode") === "retrospective" ? "period" : "search");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [source, setSource] = useState(params.get("source") ?? "");
  const [sourceState, setSourceState] = useState(params.get("source_state") ?? "");
  const [type, setType] = useState(params.get("type") ?? "");
  const [dateField, setDateField] = useState(params.get("date_field") ?? (params.get("mode") === "retrospective" ? "event_at" : "created_at"));
  const [from, setFrom] = useState(params.get("date_from") ?? "");
  const [to, setTo] = useState(params.get("date_to") ?? "");
  const [version, setVersion] = useState(params.get("mode") === "historical" ? "observed" : "current");
  const [asOf, setAsOf] = useState(params.get("as_of") ?? "");
  const [exact, setExact] = useState(params.get("exact") === "true" || (!params.has("mode") && hasSearchConditions(params)));
  const [includeWork, setIncludeWork] = useState(params.get("include_work_commentary") === "true");
  const [validation, setValidation] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(version === "observed" || exact || Boolean(sourceState) || includeWork);
  const historical = purpose === "search" && version === "observed";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (historical) {
      if (!q.trim()) { setValidation("Enter a question to review past records."); return; }
      if (!validDate(asOf) || asOf === "9999-12-31") { setValidation("Choose a valid observation cutoff date."); return; }
      const next = new URLSearchParams({ mode: "historical", q: q.trim(), as_of: asOf });
      if (source) next.set("source", source);
      if (type) next.set("type", type);
      setValidation(""); onApply(next); return;
    }
    if ((from && !validDate(from)) || (to && !validDate(to))) { setValidation("Enter a valid date in YYYY-MM-DD format."); return; }
    if (from && to && from > to) { setValidation("Start date must be on or before end date."); return; }
    if (purpose === "period" && (!from || !to || Date.parse(to) - Date.parse(from) >= 92 * 86400000)) { setValidation("Choose start and end dates within 92 days."); return; }
    setValidation("");
    const next = new URLSearchParams({ mode: purpose === "period" ? "retrospective" : "search" });
    for (const [key, value] of Object.entries({ q: purpose === "period" ? "" : q.trim(), source, source_state: purpose === "period" ? "" : sourceState, type, date_field: dateField, date_from: from, date_to: to })) {
      if (value && !(key === "date_field" && value === "created_at" && purpose !== "period")) next.set(key, value);
    }
    if (purpose === "search" && exact) next.set("exact", "true");
    if (purpose === "search" && includeWork) next.set("include_work_commentary", "true");
    onApply(next);
  }

  const activeFilters = [source, type, ...(!historical ? [dateField === "event_at" ? dateField : "", from, to] : [])].filter(Boolean).length;
  return <form noValidate className="search-form panel" onSubmit={submit} onChange={onDraftChange}>
    <div className="search-intents" role="group" aria-label="Search or review">
      <button type="button" aria-pressed={purpose === "search"} onClick={() => { if (purpose !== "search") { setPurpose("search"); setValidation(""); onDraftChange?.(); } }}>Search &amp; ask</button>
      <button type="button" aria-pressed={purpose === "period"} onClick={() => { if (purpose !== "period") { setPurpose("period"); setDateField("event_at"); setValidation(""); onDraftChange?.(); } }}>Review a period</button>
    </div>
    {purpose === "search" ? <>
      <label htmlFor="search-q">Search query</label>
      <div className="search-query-row"><input id="search-q" value={q} maxLength={256} onChange={event => setQ(event.target.value)} placeholder="Search your records or ask a question" /><button className="primary" type="submit"><Icon name="search" />Search</button></div>
      <p className="help-text">Search is local. You can request an answer with sources after reviewing your question.</p>
    </> : <p className="help-text">Choose up to 92 days to review recorded activities and decisions. Review the selected originals before requesting a summary.</p>}
    <details className="search-filter-details" open={purpose === "period" || activeFilters > 0}>
      <summary>Filters{activeFilters > 0 ? ` · ${activeFilters} active` : ""}</summary>
      <div className="search-filters">
        <label>Source<select aria-label="Source" value={source} onChange={event => setSource(event.target.value)}>
          <option value="">All sources</option>{Object.entries(sourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label>Type<select aria-label="Type" value={type} onChange={event => setType(event.target.value)}>
          <option value="">All types</option><option value="NOTE">Note</option><option value="LOG">Log</option><option value="DOCUMENT">Document</option><option value="CONVERSATION">Conversation</option><option value="PROJECT_EVENT">Project event</option>
        </select></label>
        {!historical && <>
          <label>Date field<select aria-label="Date field" value={dateField} onChange={event => setDateField(event.target.value)}><option value="created_at">Added</option><option value="event_at">Source/event date</option></select></label>
          <div><label htmlFor="start-date">Start date</label><DateInput id="start-date" label="Start date" value={from} onChange={value => { setFrom(value); onDraftChange?.(); }} /></div>
          <div><label htmlFor="end-date">End date</label><DateInput id="end-date" label="End date" value={to} onChange={value => { setTo(value); onDraftChange?.(); }} /></div>
        </>}
      </div>
      {!historical && <p className="help-text">Date ranges use Asia/Seoul and include the end date. Records without a source/event date are excluded when filtering by that date.</p>}
    </details>
    {purpose === "search" && <details className="search-filter-details" open={advancedOpen} onToggle={event => setAdvancedOpen(event.currentTarget.open)}>
      <summary>Advanced options</summary>
      <label>Record version<select aria-label="Record version" value={version} onChange={event => { setVersion(event.target.value); if (event.target.value === "observed") setExact(false); }}><option value="current">Current records</option><option value="observed">Observed by a date</option></select></label>
      {historical ? <>
        <label htmlFor="observed-through">Observed through</label><DateInput id="observed-through" label="Observed through" value={asOf} onChange={value => { setAsOf(value); onDraftChange?.(); }} />
        <p className="help-text">Uses the latest retained observation by the end of this date in Asia/Seoul. This is collection history, not the date a decision happened. Later imports are excluded even when their events are earlier. Source and type filters apply; other date and source-status filters are not used.</p>
      </> : <>
        <label className="work-search-option"><input type="checkbox" checked={exact} onChange={event => setExact(event.target.checked)} />Match exact phrase</label>
        <label>Source status<select aria-label="Source status" value={sourceState} onChange={event => setSourceState(event.target.value)}><option value="">{exact || !q.trim() ? "All retained records" : "Exclude source-deleted records"}</option>{["available", "deleted", "unavailable", "unknown"].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        <label className="work-search-option"><input type="checkbox" checked={includeWork} onChange={event => setIncludeWork(event.target.checked)} />Include Codex commands, results, diffs and commentary</label>
      </>}
    </details>}
    {purpose === "period" && <button className="primary" type="submit">Review period</button>}
    <button className="search-reset" type="button" onClick={() => onApply(new URLSearchParams())}>Reset</button>
    {validation && <p role="alert">{validation}</p>}
  </form>;
}

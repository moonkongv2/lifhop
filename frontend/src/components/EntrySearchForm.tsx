import { useState } from "react";
import type { FormEvent } from "react";
import { sourceLabels } from "../utils/entries";
import DateInput from "./DateInput";
import { validDate } from "../utils/dates";
import Icon from "./Icon";

export default function EntrySearchForm({ params, onApply }: { params: URLSearchParams; onApply: (params: URLSearchParams) => void }) {
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
    if ((from && !validDate(from)) || (to && !validDate(to))) { setValidation("Enter a valid date in YYYY-MM-DD format."); return; }
    if (from && to && from > to) { setValidation("Start date must be on or before end date."); return; }
    setValidation("");
    const next = new URLSearchParams();
    for (const [key, value] of Object.entries({ q: q.trim(), source, source_state: sourceState, type, date_field: dateField, date_from: from, date_to: to })) {
      if (value && !(key === "date_field" && value === "created_at")) next.set(key, value);
    }
    onApply(next);
  }

  const activeFilters = [source, sourceState, type, dateField === "event_at" ? dateField : "", from, to].filter(Boolean).length;
  return (
    <form noValidate className="search-form panel" onSubmit={submit}>
      <label htmlFor="search-q">Search query</label>
      <div className="search-query-row"><input id="search-q" value={q} maxLength={256} onChange={(event) => setQ(event.target.value)} placeholder="Search titles and content for phrases, names, numbers, or code" /><button className="primary" type="submit"><Icon name="search" />Search</button></div>
      <details className="search-filter-details" open={activeFilters > 0}>
        <summary>Filters{activeFilters > 0 ? ` · ${activeFilters} active` : ""}</summary>
        <div className="search-filters">
          <label>Source<select aria-label="Source" value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="">All sources</option>
            {Object.entries(sourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
          <label>Source status<select aria-label="Source status" value={sourceState} onChange={e => setSourceState(e.target.value)}>
            <option value="">All retained records</option>
            {["available", "deleted", "unavailable", "unknown"].map(value => <option key={value} value={value}>{value}</option>)}
          </select></label>
          <label>Type<select aria-label="Type" value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">All types</option><option value="NOTE">Note</option><option value="LOG">Log</option>
            <option value="DOCUMENT">Document</option><option value="CONVERSATION">Conversation</option><option value="PROJECT_EVENT">Project event</option>
          </select></label>
          <label>Date field<select aria-label="Date field" value={dateField} onChange={(event) => setDateField(event.target.value)}>
            <option value="created_at">Added</option><option value="event_at">Source/event date</option>
          </select></label>
          <div><label htmlFor="start-date">Start date</label><DateInput id="start-date" label="Start date" value={from} onChange={setFrom} /></div>
          <div><label htmlFor="end-date">End date</label><DateInput id="end-date" label="End date" value={to} onChange={setTo} /></div>
        </div>
        <p className="help-text">Date ranges use Asia/Seoul and include the end date. Records without a source/event date are excluded when filtering by that date.</p>
      </details>
      <button className="search-reset" type="button" onClick={() => onApply(new URLSearchParams())}>Reset</button>
      {validation && <p role="alert">{validation}</p>}
    </form>
  );
}

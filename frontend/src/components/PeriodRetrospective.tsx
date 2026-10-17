import { citationTarget } from "../api/passages";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { fetchAnswerStatus } from "../api/answers";
import { previewPeriod, summarizePeriod } from "../api/retrospectives";
import type { PeriodPreview } from "../api/retrospectives";
import { listContext, listTarget } from "../utils/entryNavigation";
import { formatEntryDate } from "../utils/entries";

function PeriodRun({ preview, params, available, refresh }: { preview: PeriodPreview; params: URLSearchParams; available: boolean; refresh: () => void }) {
  const [consent, setConsent] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const pending = useRef(false);
  const run = useMutation({ mutationFn: async (active: AbortController) => {
    const timeout = window.setTimeout(() => active.abort(new DOMException("The retrospective timed out. A sent request may have been charged.", "TimeoutError")), 60000);
    try { return await summarizePeriod(preview, active.signal); } finally { window.clearTimeout(timeout); }
  }, retry: false, gcTime: 0, onSettled: () => { pending.current = false; setConsent(false); refresh(); } });
  useEffect(() => () => controller.current?.abort(), []);
  const result = available && !run.isPending && run.data?.preview.preview_digest === preview.preview_digest ? run.data : undefined;
  const returnTo = listTarget(listContext("/search", params));
  return <section className="panel semantic-controls" aria-label="Period retrospective">
    <h3>Period retrospective</h3>
    <p>{preview.scope.date_from} – {preview.scope.date_to} · Asia/Seoul · {preview.scope.date_field === "event_at" ? "Source/event dates" : "Added dates (collection time)"}</p>
    <p><strong>Partial view:</strong> {preview.selected_records} original passages selected from {preview.ready_records} records with a current body index; {preview.matched_records} records match the period, {preview.allowed_records} are eligible for AI.</p>
    <p className="help-text">Records are sampled across the period, keeping the first body passage per selected record and grouping identical document passages. Additional sections and unselected records are not examined. Current retained versions are used; this does not reconstruct what was known at the time.</p>
    <ul className="help-text">
      <li>{preview.allowed_records - preview.ready_records} eligible records have no current body passage.</li>
      <li>{preview.ready_records - preview.unique_records} repeated document records are grouped; {preview.candidate_records} representative records are available for bounded selection.</li>
      <li>{preview.byte_skipped} complete passages skipped by the request size limit; {preview.incomplete_selected} selected records have incomplete coverage.</li>
      <li>{preview.missing_event_dates} records for these source/type filters have no source/event date (across all dates). {preview.scope.date_field === "event_at" ? "They are excluded from this date query." : "Added dates do not establish when their activities happened."}</li>
    </ul>
    <label className="work-search-option"><input type="checkbox" checked={consent} disabled={!available || !preview.passages.length || run.isPending} onChange={e => setConsent(e.target.checked)} />Send this period summary request and the selected original passages with their dates to OpenAI</label>
    <p className="help-text">One answer request, maximum USD 0.01. No question embedding is needed. Imported plans or commits alone do not prove completed work or deployment.</p>
    <div className="actions"><button className="primary" disabled={!available || !consent || !preview.passages.length || run.isPending}
      onClick={() => { if (pending.current) return; pending.current = true; controller.current = new AbortController(); run.reset(); run.mutate(controller.current); }}>Summarize this period</button>
      <button disabled={run.isPending} onClick={() => { setConsent(false); refresh(); }}>Refresh period preview</button>
      {run.isPending && <button onClick={() => { controller.current?.abort(); setConsent(false); }}>Stop</button>}
    </div>
    {run.isPending && <p role="status">Summarizing selected records...</p>}
    {run.error && <p role="alert">{run.error.name === "AbortError" ? "Stopped. A request already sent may still finish and be charged." : run.error.message}</p>}
    {!preview.passages.length && <p role="status">No eligible original passages were selected. No AI request will be sent.</p>}
    <p className="help-text">Each new action may incur a new charge. Stopping or leaving cannot withdraw an already sent request. Nothing repeats automatically.</p>
    {result && <div className="answer-result"><h4>{result.answer.status === "supported" ? "Draft retrospective" : "Insufficient evidence"}</h4>
      {result.answer.status === "insufficient" ? <p>{result.answer.answer}</p> : <ul>{result.answer.answer.trim().split("\n").map((line, index) => {
        const match = line.match(/^\[(\d+)\] (.*)$/);
        const citation = result.answer.citations.find(c => c.source_id === Number(match?.[1]));
        return <li key={index}>{match?.[2] ?? line}{citation && <> <Link to={citationTarget(citation.passage, returnTo)}>[{citation.source_id}] {citation.passage.title}</Link></>}</li>;
      })}</ul>}
      <p className="help-text">Check every category and claim against its original. This draft covers only the selected passages.</p>
    </div>}
    <details><summary>Review {preview.passages.length} selected original passages</summary>{preview.passages.map(p => <article key={p.id}>
      <h4>{p.title}</h4><p className="help-text">Source/event: {formatEntryDate(p.event_at)} · Added: {formatEntryDate(p.created_at)} · Version {p.version_id}</p>
      <p className="entry-content">{p.text}</p><Link to={citationTarget(p, returnTo)}>Open original · Characters {p.start+1}–{p.end}</Link>
    </article>)}</details>
  </section>;
}

export default function PeriodRetrospective({ params }: { params: URLSearchParams }) {
  const serialized = params.toString();
  const period = useQuery({ queryKey: ["period-preview", serialized], queryFn: ({ signal }) => previewPeriod(new URLSearchParams(serialized), signal), retry: false, gcTime: 0 });
  const answers = useQuery({ queryKey: ["answer-status"], queryFn: ({ signal }) => fetchAnswerStatus(signal), retry: false, gcTime: 0 });
  const fresh = !period.isFetching && !answers.isFetching;
  const sameRevision = period.data && period.data.policy_revision === answers.data?.policy_revision;
  const refresh = () => { void period.refetch(); void answers.refetch(); };
  return <>
    {!fresh && <p role="status">Reviewing the selected period locally...</p>}
    {(period.error || answers.error) && <p role="alert">{period.error?.message ?? answers.error?.message}</p>}
    {answers.data && !answers.data.enabled && <p role="status">Answer generation is disabled on this server. The preview makes no AI request.</p>}
    {period.data && answers.data && !sameRevision && <p role="status">Records or permissions changed. Refresh the period preview before summarizing.</p>}
    {sameRevision && period.data && !period.error && !answers.error ? <PeriodRun key={period.data.preview_digest} preview={period.data} params={params}
      available={fresh && answers.data?.enabled === true} refresh={refresh} /> : <button onClick={refresh}>Refresh period preview</button>}
  </>;
}

import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { answerHistory, historyCitationTarget, previewHistory, type HistoryPreview } from '../api/historical';
import { fetchAnswerStatus } from '../api/answers';
import { listContext, listTarget } from '../utils/entryNavigation';
import { formatEntryDate } from '../utils/entries';

function HistoryRun({ preview, params, available, refresh }: { preview: HistoryPreview; params: URLSearchParams; available: boolean; refresh: () => void }) {
  const [consent, setConsent] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const pending = useRef(false);
  const run = useMutation({ mutationFn: async (active: AbortController) => {
    const timeout = window.setTimeout(() => active.abort(new DOMException('The answer timed out. A sent request may have been charged.', 'TimeoutError')), 60000);
    try { return await answerHistory(preview, active.signal); } finally { window.clearTimeout(timeout); }
  }, retry: false, gcTime: 0, onSettled: () => { pending.current = false; setConsent(false); refresh(); } });
  useEffect(() => () => controller.current?.abort(), []);
  const result = available && !run.isPending && run.data?.preview.preview_digest === preview.preview_digest ? run.data : undefined;
  const returnTo = listTarget(listContext('/search', params));
  return <section className="panel semantic-controls" aria-label="Historical question">
    <h3>Historical question</h3><p>{preview.scope.q}</p>
    <p><strong>Observed through {preview.scope.as_of}</strong> · Asia/Seoul · Latest retained observation per record by the end of this date.</p>
    <p className="help-text">This is collection history, not proof of what happened or what the external source contained on that day. Later imports are excluded even if their event date is earlier. Restoring a version does not reconstruct a past selection.</p>
    <p><strong>Partial view:</strong> {preview.observed_records} of {preview.scope_records} scoped records have an observation by this date; {preview.allowed_records} are eligible for AI; {preview.matching_records} have keyword matches in the selected version.</p>
    <p className="help-text">Up to 20 newest matching versions are candidates; {preview.examined_records} were examined and {preview.passages.length} complete excerpts selected (at most five, one per record). Only the first matching passage per examined record is considered. Local keyword matching can miss different wording or languages. {preview.input_skipped} versions were too large or could not be read reliably; {preview.byte_skipped} excerpts exceeded the request size limit. Other sections or records may be missed.</p>
    {!preview.passages.length && <p role="status">No eligible historical excerpts were selected. No AI request will be sent.</p>}
    {preview.passages.map(p => <article key={p.version_id}><h4>{p.title}</h4>
      <p className="help-text">Observed: {formatEntryDate(p.observed_at)} · Source/event: {formatEntryDate(p.event_at)} · Version {p.version_id}{p.completeness !== 'complete' ? ' · Incomplete source' : ''}</p>
      <p className="entry-content">{p.text}</p><Link to={historyCitationTarget(p, returnTo)}>View historical original · Version {p.version_id}</Link>
    </article>)}
    <label className="work-search-option"><input type="checkbox" checked={consent} disabled={!available || !preview.passages.length || run.isPending}
      onChange={e => setConsent(e.target.checked)} />Send this question, observation cutoff and the displayed historical excerpts with their dates to OpenAI</label>
    <p className="help-text">One answer call, maximum USD 0.01; no query embedding. Each new action may incur a charge. Stopping cannot withdraw a sent request. Nothing repeats automatically.</p>
    <div className="actions"><button className="primary" disabled={!available || !consent || !preview.passages.length || run.isPending}
      onClick={() => { if (pending.current) return; pending.current = true; controller.current = new AbortController(); run.reset(); run.mutate(controller.current); }}>Answer from historical excerpts</button>
      <button disabled={run.isPending} onClick={() => { setConsent(false); refresh(); }}>Refresh history preview</button>
      {run.isPending && <button onClick={() => { controller.current?.abort(); setConsent(false); }}>Stop</button>}
    </div>
    {run.isPending && <p role="status">Checking historical evidence...</p>}
    {run.error && <p role="alert">{run.error.name === 'AbortError' ? 'Stopped. A sent request may still finish and be charged.' : run.error.message}</p>}
    {result && <div className="answer-result"><h4>{result.status === 'supported' ? 'Draft historical answer' : 'Insufficient evidence'}</h4><p>{result.answer}</p>
      <p className="help-text">Verify the conclusion against the cited observations. These excerpts do not reconstruct the entire past.</p>
      {result.citations.length > 0 && <ul>{result.citations.map(p => <li key={p.version_id}><Link to={historyCitationTarget(p, returnTo)}>{p.title} · Version {p.version_id}</Link></li>)}</ul>}
    </div>}
  </section>;
}

export default function HistoricalQuestion({ params }: { params: URLSearchParams }) {
  const serialized = params.toString();
  const token = localStorage.getItem("access_token");
  const preview = useQuery({ queryKey: ['history-preview', token, serialized], queryFn: ({ signal }) => previewHistory(new URLSearchParams(serialized), signal), retry: false, gcTime: 0 });
  const status = useQuery({ queryKey: ['answer-status', token], queryFn: ({ signal }) => fetchAnswerStatus(signal), retry: false, gcTime: 0 });
  const fresh = !preview.isFetching && !status.isFetching;
  const sameRevision = preview.data && preview.data.policy_revision === status.data?.policy_revision;
  const refresh = () => { void preview.refetch(); void status.refetch(); };
  return <>{(!fresh || !preview.data) && !preview.error && <p role="status">Reviewing local history...</p>}
    {preview.error && <p role="alert">{preview.error.message}</p>}{status.error && <p role="alert">{status.error.message}</p>}
    {status.data && !status.data.enabled && <p role="status">Answer generation is disabled on this server. The history preview is local.</p>}
    {fresh && preview.data && status.data && !sameRevision && <p role="alert">Records or permissions changed. Review history again.</p>}
    {(!preview.data || !sameRevision || preview.error || status.error) && <button onClick={refresh} disabled={!fresh}>Refresh history preview</button>}
    {!preview.error && !status.error && sameRevision && preview.data && <HistoryRun key={preview.data.preview_digest} preview={preview.data}
      params={params} available={fresh && Boolean(status.data?.enabled)} refresh={refresh} />}
  </>;
}

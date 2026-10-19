import { citationTarget } from "../api/passages";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { fetchAnswerStatus } from "../api/answers";
import { askFromRecords } from "../api/questions";
import type { QuestionStage } from "../api/questions";
import { fetchSemanticStatus } from "../api/semantic";
import { listContext, listTarget } from "../utils/entryNavigation";
import SemanticResults from "./SemanticResults";

const stages = { search: "Finding related records...", evidence: "Choosing original passages locally...", answer: "Generating an answer with sources..." };

function QuestionRun({ params, revision, available, refresh, productView }: { params: URLSearchParams; revision: number; available: boolean; refresh: () => void; productView: boolean }) {
  const [consent, setConsent] = useState(false);
  const [stage, setStage] = useState<QuestionStage>("search");
  const controller = useRef<AbortController | null>(null);
  const pending = useRef(false);
  const run = useMutation({ mutationFn: async (active: AbortController) => {
    const timer = window.setTimeout(() => active.abort(new DOMException(
      "The question timed out. A request already sent may have been charged.", "TimeoutError")), 60000);
    try {
      return await askFromRecords(params, revision, active.signal, setStage);
    } finally { window.clearTimeout(timer); }
  }, retry: false, gcTime: 0, onSettled: () => { pending.current = false; setConsent(false); refresh(); } });
  useEffect(() => () => { controller.current?.abort(); }, []);
  const result = available && !run.isPending ? run.data : undefined;
  const returnTo = listTarget(listContext("/search", params));
  return <section className="panel semantic-controls" aria-label="Answer with sources">
    <h3>Answer with sources</h3>
    <p><strong>Question:</strong> {params.get("q")}</p>
    <p className="help-text">This action searches current AI-allowed records matching the filters above, chooses up to five original passages, and generates a cited draft. Work logs and source-deleted records are excluded. Up to two AI requests, maximum USD 0.011 in total. Each new action can incur another charge.</p>
    <label className="work-search-option"><input type="checkbox" checked={consent} disabled={!available || run.isPending}
      onChange={e => setConsent(e.target.checked)} />Allow OpenAI to receive this question for search and answering, plus up to five automatically selected original passages</label>
    <div className="actions"><button className="primary" disabled={!consent || !available || run.isPending}
      onClick={() => { if (pending.current) return; pending.current = true; controller.current = new AbortController(); run.reset(); run.mutate(controller.current); }}>Ask from my records</button>
      <button disabled={run.isPending} onClick={() => { setConsent(false); refresh(); }}>Refresh availability</button>
      {run.isPending && <button onClick={() => { controller.current?.abort(); setConsent(false); }}>Stop</button>}
    </div>
    {run.isPending && <p role="status">{stages[stage]}</p>}
    <p className="help-text">Stopping or leaving this screen prevents later stages. A request already sent may still finish and be charged. No stage repeats automatically.</p>
    {run.error && <p role="alert">{run.error.name === "AbortError" ? "Stopped. No later stage will run. A request already sent may have been charged." : `${run.error.message} No automatic retry will be made.`}</p>}
    {result && <>
      {result.answer ? <div className="answer-result"><h4>{result.answer.status === "supported" ? "Draft answer" : result.answer.status === "partial" ? "Partial draft — some requested facts are unconfirmed" : "Insufficient evidence"}</h4>
        <p className="entry-content">{result.answer.answer}</p>
        <p className="help-text">Verify claims against the cited originals. Only part of your archive may have been examined.</p>
        {result.answer.citations.length > 0 && <ul>{result.answer.citations.map(c => <li key={`${c.kind}-${c.source_id}`}>
          <Link to={citationTarget(c.passage, returnTo)}>{c.passage.title} · Version {c.passage.version_id} · Characters {c.passage.start+1}–{c.passage.end}</Link>
        </li>)}</ul>}
      </div> : <p role="status">No usable evidence was selected. No answer request was sent. {productView ? "Check the question and filters." : "Check the filters or use manual evidence review."}</p>}
      {result.proposal && <details><summary>Review {result.proposal.passages.length} passages used for this answer</summary>
        {result.proposal.passages.map(p => <article key={p.id}><h4>{p.title}</h4><p className="entry-content">{p.text}</p>
          <Link to={citationTarget(p, returnTo)}>Open original passage · Characters {p.start+1}–{p.end}</Link></article>)}
        {result.proposal.omissions.length > 0 && <p className="help-text">{result.proposal.omissions.length} matches were omitted because they repeated a parent passage or exceeded the selection/size limits.</p>}
      </details>}
    </>}
  </section>;
}

export default function QuestionAnswer({ params, productView = false }: { params: URLSearchParams; productView?: boolean }) {
  const [manual, setManual] = useState(false);
  const serialized = params.toString();
  const token = localStorage.getItem("access_token");
  const coverage = useQuery({ queryKey: ["semantic-status", token, serialized], queryFn: ({ signal }) => fetchSemanticStatus(new URLSearchParams(serialized), signal), retry: false, gcTime: 0 });
  const answers = useQuery({ queryKey: ["answer-status", token], queryFn: ({ signal }) => fetchAnswerStatus(signal), retry: false, gcTime: 0 });
  const fresh = !coverage.isFetching && !answers.isFetching;
  const revision = coverage.data?.policy_revision;
  const sameRevision = revision !== undefined && revision === answers.data?.policy_revision;
  const ready = coverage.data?.state === "available" && answers.data?.enabled === true;
  const refresh = () => { void coverage.refetch(); void answers.refetch(); };
  return <section aria-label="Question and sources">
    {(coverage.isFetching || answers.isFetching) && <p role="status">Checking available records and permissions...</p>}
    {(coverage.error || answers.error) && <p role="alert">{coverage.error?.message ?? answers.error?.message}</p>}
    {coverage.data && <p className="help-text">{coverage.data.indexed_records} records are ready for answers with these filters. Coverage may be partial.</p>}
    {fresh && !ready && <p role="status">AI answers are unavailable for these filters. You can still search your records.</p>}
    {fresh && coverage.data && answers.data && !sameRevision && <p role="status">Records or permissions changed. Refresh availability before asking.</p>}
    {!sameRevision || coverage.error || answers.error ? <button onClick={refresh}>Refresh availability</button>
      : !manual && <QuestionRun key={`${revision}`} params={params} revision={revision!} available={fresh && ready} refresh={refresh} productView={productView} />}
    {!productView && <button aria-expanded={manual} onClick={() => setManual(!manual)}>{manual ? "Return to automatic answer" : "Choose evidence manually (advanced)"}</button>}
    {!productView && manual && <SemanticResults params={params} />}
  </section>;
}

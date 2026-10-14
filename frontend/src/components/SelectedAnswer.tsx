import { useState } from "react";
import { Link } from "react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchAnswerStatus, requestAnswer } from "../api/answers";
import { listContext, listTarget } from "../utils/entryNavigation";

export default function SelectedAnswer({ question, selected, params }: { question: string; selected: number[]; params: URLSearchParams }) {
  const [consent, setConsent] = useState(false);
  const status = useQuery({ queryKey: ["answer-status"], queryFn: ({signal}) => fetchAnswerStatus(signal), retry: false, gcTime: 0 });
  const answer = useMutation({ mutationFn: () => requestAnswer(question, selected), retry: false,
    onSettled: () => { setConsent(false); void status.refetch(); } });
  const result = !status.isFetching && !status.error && status.data && answer.data?.policy_revision === status.data.policy_revision ? answer.data : undefined;
  const returnTo = listTarget(listContext("/search", params));
  return <section className="panel semantic-controls" aria-label="Cited answer">
    <h3>Answer from selected passages</h3>
    <p className="help-text">Select up to five exact passages above and review their text. The answer will use only those passages; verify every claim against its citations. Each answer request is limited to USD 0.01.</p>
    <p>{selected.length} of 5 passages selected</p>
    {status.isFetching && <p role="status">Checking answer availability...</p>}
    {status.error && <p role="alert">{status.error.message}</p>}
    {status.data && !status.data.enabled && <p role="status">Answer generation is disabled on this server.</p>}
    <label className="work-search-option"><input type="checkbox" checked={consent} disabled={!status.data?.enabled || answer.isPending}
      onChange={e => setConsent(e.target.checked)} />Send this question and the selected passages to OpenAI for an answer</label>
    <button className="primary" disabled={!consent || !selected.length || !status.data?.enabled || status.isFetching || Boolean(status.error) || answer.isPending}
      onClick={() => { answer.reset(); answer.mutate(); }}>Generate cited answer</button>
    {answer.isPending && <p role="status">Checking the selected evidence...</p>}
    {answer.error && <p role="alert">{answer.error.message}</p>}
    {result && <div className="answer-result"><h4>{result.status === "supported" ? "Draft answer" : "Insufficient evidence"}</h4>
      <p>{result.answer}</p>
      {result.citations.length > 0 && <ul>{result.citations.map(c =>
        <li key={c.embedding_id}><Link to={`/semantic/slices/${c.embedding_id}?${new URLSearchParams({ returnTo })}`}>
          {c.passage.title} · Version {c.passage.version_id} · Characters {c.passage.start+1}–{c.passage.end}
        </Link></li>)}</ul>}
    </div>}
  </section>;
}

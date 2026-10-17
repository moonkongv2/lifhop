import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router";
import { recommendPassages } from "../api/answers";
import { listContext, listTarget } from "../utils/entryNavigation";
import SelectedAnswer from "./SelectedAnswer";

const reasons = { duplicate_parent: "same original passage", count_limit: "five-passage limit", byte_limit: "request size limit" };

export default function RecommendedPassages({ ids, revision, params }: { ids: number[]; revision: number; params: URLSearchParams }) {
  const controller = useRef<AbortController | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const proposal = useMutation({ mutationFn: () => {
    controller.current = new AbortController();
    return recommendPassages(params, ids, revision, controller.current.signal);
  }, retry: false, onSuccess: data => setSelected(data.passages.map(p => p.id)) });
  useEffect(() => () => controller.current?.abort(), []);
  const returnTo = listTarget(listContext("/search", params));
  return <>
    <section className="panel semantic-controls" aria-label="Recommended evidence">
      <h3>Recommend passages</h3>
      <p className="help-text">Expand these search matches to their original passages and propose up to five in similarity order. Review the full text before requesting an answer. This step runs locally and makes no AI request.</p>
      <button disabled={proposal.isPending || !ids.length} onClick={() => { setSelected([]); proposal.reset(); proposal.mutate(); }}>Recommend passages</button>
      {proposal.isPending && <p role="status">Preparing passages locally...</p>}
      {proposal.error && <p role="alert">{proposal.error.message}</p>}
      {proposal.data && <>
        <p role="status">{proposal.data.passages.length} original passages proposed. Supporting evidence may still be missing.</p>
        {proposal.data.passages.map(p => <article className="answer-result" key={p.id}>
          <h4>{p.title}</h4><p className="entry-content">{p.text}</p>
          <label className="work-search-option"><input type="checkbox" checked={selected.includes(p.id)} onChange={e => setSelected(current => e.target.checked ? [...current, p.id] : current.filter(id => id !== p.id))} />Include original passage {p.id}</label>
          <p className="help-text">Version {p.version_id} · Characters {p.start+1}–{p.end}</p>
          <Link to={`/passages/${p.id}?${new URLSearchParams({ returnTo })}`}>View original passage</Link>
        </article>)}
        {!proposal.data.passages.length && <p>No complete passages fit this request. Select individual matches below.</p>}
        {proposal.data.omissions.length > 0 && <details><summary>{proposal.data.omissions.length} search {proposal.data.omissions.length === 1 ? "match" : "matches"} omitted from this proposal</summary>
          <ul>{proposal.data.omissions.map(o => <li key={o.embedding_id}>Match {o.rank}: {reasons[o.reason]}</li>)}</ul>
        </details>}
      </>}
    </section>
    {proposal.data && <SelectedAnswer key={selected.join(",")} question={params.get("q") ?? ""} selected={selected} params={params} kind="passage" />}
  </>;
}

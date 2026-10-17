import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { fetchSemanticLocations, fetchSemanticStatus, searchSemantic } from "../api/semantic";
import type { SemanticResponse } from "../api/semantic";
import { entryTarget, listContext, listTarget } from "../utils/entryNavigation";
import { formatEntryDate, sourceLabels } from "../utils/entries";
import SelectedAnswer from "./SelectedAnswer";
import RecommendedPassages from "./RecommendedPassages";

function target(id: number, params: URLSearchParams) {
  return `/semantic/slices/${id}?${new URLSearchParams({ returnTo: listTarget(listContext("/search", params)) })}`;
}

function Locations({ hit, params }: { hit: SemanticResponse["items"][number]; params: URLSearchParams }) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const serialized = params.toString();
  const { data, error, isFetching } = useQuery({ queryKey: ["semantic-locations", hit.embedding_id, serialized, offset],
    queryFn: ({ signal }) => fetchSemanticLocations(hit.embedding_id, new URLSearchParams(serialized), offset, signal), enabled: open, retry: false, gcTime: 0 });
  if (hit.passage.alias_total <= 1) return null;
  return <div className="passage-snapshots"><button aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide locations" : `View ${hit.passage.alias_total} retained locations`}</button>
    {open && <>{isFetching && <p role="status">Loading locations...</p>}{error && <p role="alert">{error.message}</p>}
      {data && !isFetching && !error && <><ul>{data.items.map(item => <li key={item.embedding_id}><Link to={target(item.embedding_id, params)}>Record {item.entry_id} · {formatEntryDate(item.event_at)}</Link></li>)}</ul>
        <div className="actions"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset-20))}>Previous locations</button><button disabled={offset+20 >= data.total} onClick={() => setOffset(offset+20)}>Next locations</button></div></>}
    </>}
  </div>;
}

const states = {
  available: "Stored slices are available for semantic search.",
  disabled: "Semantic search is disabled. Exact phrase and Passages remain available.",
  unavailable: "Semantic search is not configured. Exact phrase and Passages remain available.",
  indexing: "Approved indexing is still in progress. No question will be sent until stored slices are available.",
  unindexed: "No allowed stored slices match these filters. Activate indexing or choose other filters. No question has been sent.",
};

export default function SemanticResults({ params }: { params: URLSearchParams }) {
  const serialized = params.toString();
  const [consent, setConsent] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [recommendation, setRecommendation] = useState(false);
  const status = useQuery({ queryKey: ["semantic-status", serialized], queryFn: ({ signal }) => fetchSemanticStatus(new URLSearchParams(serialized), signal), retry: false, gcTime: 0 });
  const search = useMutation({ mutationFn: () => searchSemantic(new URLSearchParams(serialized)), retry: false,
    onMutate: () => { setSelected([]); setRecommendation(false); },
    onSettled: () => { setConsent(false); void status.refetch(); } });
  const coverage = status.data;
  const result = !search.isPending && !status.isFetching && !status.error && search.data && coverage?.policy_revision === search.data.coverage.policy_revision ? search.data : undefined;
  return <section aria-label="Semantic search">
    <div className="panel semantic-controls"><h3>Semantic search</h3>
      {status.isFetching && <p role="status">Checking current index...</p>}{status.error && <p role="alert">{status.error.message}</p>}
      {coverage && <><p role="status">{states[coverage.state]}</p>
        <p className="help-text">{coverage.ready_slices} stored slices across {coverage.indexed_records} records · {coverage.allowed_records} AI-allowed records · {coverage.matched_records} records match the filters.</p>
        <p className="help-text">Coverage may be partial. Only current allowed stored slices are searched; work logs and source-deleted records are excluded.</p>
        {Object.keys(coverage.jobs).length > 0 && <p className="help-text">Indexing jobs: {Object.entries(coverage.jobs).map(([state, count]) => `${count} ${state}`).join(" · ")}</p>}
      </>}
      <button disabled={status.isFetching || search.isPending} onClick={() => void status.refetch()}>Refresh index status</button>
      <label className="work-search-option"><input type="checkbox" checked={consent} disabled={search.isPending} onChange={e => setConsent(e.target.checked)} />Send this question to OpenAI for this search</label>
      <p className="help-text">One paid question-embedding request; stored document text is searched locally. No AI answer is generated. Returning here never repeats a paid search.</p>
      <button className="primary" disabled={!consent || coverage?.state !== "available" || status.isFetching || Boolean(status.error) || search.isPending} onClick={() => { search.reset(); search.mutate(); }}>Search with OpenAI</button>
      {search.isPending && <p role="status">Finding related passages...</p>}{search.error && <p role="alert">{search.error.message}</p>}
      {search.data && coverage && coverage.policy_revision !== search.data.coverage.policy_revision && <p role="status">Records or permissions changed. Review the index status and submit a new search.</p>}
    </div>
    {result && <><div className="records-toolbar"><p>{result.items.length} related passages{result.truncated ? " · First 20 results" : ""}</p><span>Similarity order · Relevance is not guaranteed</span></div>
      {result.items.length > 0 && <div className="panel semantic-controls">
        <button onClick={() => { setSelected([]); setRecommendation(!recommendation); }}>{recommendation ? "Use individual search matches" : "Review original passage recommendations"}</button>
        <p className="help-text">Choose original passage recommendations or select individual matches below.</p>
      </div>}
      {recommendation && <RecommendedPassages key={`${search.submittedAt}-${result.coverage.policy_revision}`} ids={result.items.map(h => h.embedding_id)} revision={result.coverage.policy_revision} params={params} />}
      {result.items.length === 0 && <div className="panel empty-state"><h3>No passages available</h3><p>Check the index status and filters. No automatic retry will be made.</p></div>}
      <div className="records-grid">{result.items.map(hit => { const p = hit.passage; return <article className="panel record-card" key={hit.embedding_id}>
        <div className="badges"><span className="badge source">{sourceLabels[p.source as keyof typeof sourceLabels] ?? p.source}</span><span className="badge">Semantic match</span>{(p.index_status === "partial" || p.completeness !== "complete") && <span className="badge">Incomplete coverage</span>}</div>
        <h3>{p.title}</h3><p className="entry-content">{p.text}</p>
        <label className="work-search-option"><input type="checkbox" checked={selected.includes(hit.embedding_id)}
          disabled={!selected.includes(hit.embedding_id) && selected.length >= 5}
          onChange={e => { setRecommendation(false); setSelected(current => e.target.checked ? [...current, hit.embedding_id] : current.filter(id => id !== hit.embedding_id)); }} />Use this passage for an answer</label>
        <p className="record-date">Source/event date: {formatEntryDate(p.event_at)} · Version {p.version_id} · Characters {p.start+1}–{p.end}</p>
        <div className="actions"><Link to={target(hit.embedding_id, params)}>View passage</Link><Link to={entryTarget(p.entry_id, listContext("/search", params))}>Open record</Link></div>
        <Locations hit={hit} params={params} />
      </article>; })}</div>
      {!recommendation && <SelectedAnswer key={`${search.submittedAt}-${selected.join(",")}`} question={params.get("q") ?? ""} selected={selected} params={params} kind="embedding" />}
    </>}
  </section>;
}

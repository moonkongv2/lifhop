import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { historyRequest } from "../api/history";
import type { components } from "../api/generated/schema";
import { formatEntryDate } from "../utils/entries";

type Run = components["schemas"]["RunResponse"];
const statusLabels: Record<string, string> = {
  active: "Collecting", disconnected: "Disconnected — resume from your Mac",
  completed: "Completed", partial: "Partially completed", failed: "Failed", empty: "No selected turns",
};

export default function CollectionRuns() {
  const [offset, setOffset] = useState(0);
  const enabled = Boolean(localStorage.getItem("access_token"));
  const runs = useQuery({ queryKey: ["collection-runs", offset],
    queryFn: () => historyRequest<Run[]>(`/collection-runs?provider=codex&limit=20&offset=${offset}`),
    enabled, refetchInterval: 5000 });
  return <section aria-label="Codex historical backfills">
    <h3>Codex historical backfills</h3>
    <p>Run the collector on your Mac to preview and apply selected history. Collection is manual; it stops when the command exits. Stored records stay searchable while your Mac is offline.</p>
    {runs.isLoading && <p role="status">Loading collection results...</p>}
    {runs.error && <><p role="alert">{runs.error.message}</p><button onClick={() => void runs.refetch()}>Retry collection results</button></>}
    {runs.data?.length === 0 && <p>No backfill runs on this page.</p>}
    {runs.data?.map(run => <article key={run.id}>
      <h4>Backfill #{run.id} · {statusLabels[run.status] ?? run.status}</h4>
      <p>Source: {run.scope}</p>
      <p>Started: {formatEntryDate(run.started_at)}<br />Last contact: {formatEntryDate(run.last_seen_at)}<br />Finished: {formatEntryDate(run.completed_at)}</p>
      <p>Sessions: {run.coverage.discovered} discovered · {run.coverage.selected} selected · {run.coverage.excluded} excluded · {run.coverage.read} read · {run.coverage.failed} failed · {run.coverage.deferred} deferred.</p>
      <p>Turns: {run.counts.new ?? 0} new · {run.counts.unchanged ?? 0} unchanged · {run.counts.updated ?? 0} updated · {run.counts.retained ?? 0} retained for review · {run.counts.blocked ?? 0} blocked · {run.counts.failed ?? 0} failed. Expected: {run.expected_items}.</p>
      {run.coverage.gaps.length > 0 && <details><summary>Collection gaps</summary><ul>
        {run.coverage.gaps.map(code => <li key={code}>{code.replaceAll("_", " ").toLowerCase()}</li>)}
      </ul></details>}
      <p>A completed run covers its selected snapshot. It does not establish that all source history is current or recover records missing from the source.</p>
    </article>)}
    <div className="actions">
      <button disabled={offset === 0 || runs.isFetching} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous backfills</button>
      <button disabled={runs.data?.length !== 20 || runs.isFetching} onClick={() => setOffset(offset + 20)}>Next backfills</button>
    </div>
  </section>;
}

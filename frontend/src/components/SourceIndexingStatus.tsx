import { useQuery } from "@tanstack/react-query";
import { historyRequest } from "../api/history";
import type { Policy } from "../api/history";
import type { components } from "../api/generated/schema";

type Run = components["schemas"]["IndexingRunResponse"];

export default function SourceIndexingStatus({ policies }: { policies: Policy[] }) {
  const runs = useQuery({ queryKey: ["source-indexing-runs"],
    queryFn: () => historyRequest<Run[]>("/indexing/runs"), refetchInterval: 30000 });
  return <section aria-label="AI indexing status">
    <h3>AI indexing status</h3>
    <p>Collection and AI indexing run separately. This view only reads the latest 50 registered indexing runs across your sources; it does not start or retry AI work. Run completion does not prove all source records are indexed or that answers are correct.</p>
    {runs.isLoading && <p role="status">Loading indexing status...</p>}
    {runs.error && <><p role="alert">Indexing status unavailable: {runs.error.message}</p>
      <button onClick={() => void runs.refetch()}>Retry loading indexing status</button></>}
    {runs.data && policies.map(policy => {
      const selected = runs.data.filter(run => run.provider === policy.provider && run.scope === policy.scope);
      return <article key={policy.id}>
        <h4>Indexing · {policy.provider} · {policy.scope}</h4>
        <p>External AI for source: {policy.external_ai_allowed ? "allowed; record permission and explicit indexing approval are also required" : "disabled; new AI work is blocked"}.</p>
        {selected.length === 0 && <p>No indexing runs for this source in the returned recent history. Existing index coverage is not established by this list.</p>}
        {selected.map(run => <div key={run.id}>
          <p>Indexing run {run.id}: {run.status}. {run.follow_changes ? "Follows selected changes." : "Fixed selection."}</p>
          <p>Indexing jobs: {Object.entries(run.counts).map(([status, count]) => `${count} ${status}`).join(" · ") || "none"}.</p>
          {run.error_code && <p>Indexing reason: {run.error_code}. Review the indexing run and its budget or permissions before any separately approved retry.</p>}
          {(run.counts.uncertain ?? 0) > 0 && <p>Some indexing calls have an uncertain outcome. Check usage accounting before approving another attempt; a retry may incur another charge.</p>}
        </div>)}
      </article>;
    })}
  </section>;
}

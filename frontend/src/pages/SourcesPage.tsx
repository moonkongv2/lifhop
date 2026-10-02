import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router";
import { historyRequest } from "../api/history";
import type { Policy, Suppression } from "../api/history";

export default function SourcesPage() {
  const cache = useQueryClient();
  const enabled = Boolean(localStorage.getItem("access_token"));
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => historyRequest<Policy[]>("/sources"), enabled });
  const suppressed = useQuery({ queryKey: ["suppressed"], queryFn: () => historyRequest<Suppression[]>("/sources/suppressed/records"), enabled });
  const purges = useQuery({ queryKey: ["purges"], queryFn: () => historyRequest<{ pending: number; failed_attempts: number; errors: string[] }>("/sources/purges/status"), enabled, refetchInterval: 5000 });
  const change = useMutation({
    mutationFn: ({ path, data, method }: { path: string; data: unknown; method: string }) => historyRequest(path, data, method),
    onSuccess: async () => { await cache.invalidateQueries({ queryKey: ["sources"] }); await cache.invalidateQueries({ queryKey: ["suppressed"] }); },
  });
  if (!enabled) return <Navigate to="/login" replace />;
  return <>
    <h2>Sources and deletion policy</h2>
    <p>Collection controls incoming records. External AI permission is separate and also requires each record to be allowed. Storage permission does not grant AI permission.</p>
    <p>Existing records remain available for local viewing and search when collection is paused. Sources appear after the first import.</p>
    {sources.isLoading && <p role="status">Loading sources...</p>}
    {sources.data?.length === 0 && <p>No sources yet. Import a record first.</p>}
    {sources.data?.map(policy => <article key={policy.id}>
      <h3>{policy.provider} · {policy.scope}</h3>
      {(["collection_enabled", "external_ai_allowed"] as const).map(field => <label key={field}>
        <input type="checkbox" checked={policy[field]} disabled={change.isPending} onChange={e => change.mutate({
          path: `/sources/${policy.id}`, method: "PATCH", data: { collection_enabled: policy.collection_enabled, external_ai_allowed: policy.external_ai_allowed, [field]: e.target.checked },
        })} />{field === "collection_enabled" ? "Allow collection" : "Allow external AI for this source"}
      </label>)}
    </article>)}
    <h3>Blocked from reimport</h3>
    <p>Deleting in lifhop removes all versions and annotations. Only source identifiers remain. Allowing reimport does not restore deleted content.</p>
    {suppressed.isLoading && <p role="status">Loading deletion records...</p>}
    {suppressed.data?.length === 0 && <p>No blocked records.</p>}
    {suppressed.data?.map(record => <article key={record.id}><p>{record.provider}: {record.external_id}</p>
      <button disabled={change.isPending} onClick={() => {
        if (window.confirm("Allow this source record to be imported again? It will start with external AI disabled.")) change.mutate({ path: `/sources/suppressed/${record.id}/allow-reimport`, data: {}, method: "POST" });
      }}>Allow reimport</button></article>)}
    <h3>Original-file purge</h3>
    {purges.data && <p>Pending objects: {purges.data.pending}. Failed attempts: {purges.data.failed_attempts}.</p>}
    <p>The import worker removes originals. Deleting one record blocks and purges its entire shared ZIP; other retained record text stays available. Pending attachment uploads wait 11 minutes for upload links to expire.</p>
    {[sources.error, suppressed.error, purges.error, change.error].filter(Boolean).map((error, index) => <p role="alert" key={index}>{error!.message}</p>)}
    {(sources.error || suppressed.error || purges.error) && <button onClick={() => { void sources.refetch(); void suppressed.refetch(); void purges.refetch(); }}>Retry loading policies</button>}
  </>;
}

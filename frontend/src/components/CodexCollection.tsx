import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { historyRequest } from "../api/history";
import type { Policy } from "../api/history";
import type { components } from "../api/generated/schema";
import { formatEntryDate } from "../utils/entries";
import CollectionRecovery from "./CollectionRecovery";

type Source = components["schemas"]["CodexSubscriptionResponse"];
const lines = (text: string) => text.split("\n").map(value => value.trim()).filter(Boolean);

function Selection({ source, disabled, save }: { source: Source; disabled: boolean;
  save: (config: Source["config"]) => void }) {
  const [cwd, setCwd] = useState(source.config.include_cwd?.join("\n") ?? "");
  const [threads, setThreads] = useState(source.config.threads?.join("\n") ?? "");
  const [excludedCwd, setExcludedCwd] = useState(source.config.exclude_cwd?.join("\n") ?? "");
  const [excludedThreads, setExcludedThreads] = useState(source.config.exclude_thread?.join("\n") ?? "");
  return <form onSubmit={event => { event.preventDefault(); save({ ...source.config,
    include_cwd: lines(cwd), threads: lines(threads), exclude_cwd: lines(excludedCwd), exclude_thread: lines(excludedThreads) }); }}>
    <label>Selected CWD roots for device {source.id}<textarea value={cwd} onChange={e => setCwd(e.target.value)} /></label>
    <label>Selected threads for device {source.id}<textarea value={threads} onChange={e => setThreads(e.target.value)} /></label>
    <label>Excluded CWD roots for device {source.id}<textarea value={excludedCwd} onChange={e => setExcludedCwd(e.target.value)} /></label>
    <label>Excluded threads for device {source.id}<textarea value={excludedThreads} onChange={e => setExcludedThreads(e.target.value)} /></label>
    <p>Changing selection pauses collection, cancels current work and revokes collector tokens. Existing records remain.</p>
    <button disabled={disabled}>Save device selection</button>
  </form>;
}

function Device({ source, allowed, pending, change, download }: { source: Source; allowed: boolean | undefined; pending: boolean;
  change: (path: string, data: unknown, method?: "POST" | "PATCH" | "DELETE") => void; download: () => void }) {
  const [interval, setInterval] = useState(String(source.interval_seconds));
  const active = source.job && ["pending", "running"].includes(source.job.status);
  const base = `/collection-subscriptions/${source.id}`;
  return <article>
    <h4>Device {source.scope}</h4>
    <p>Subscription ID: {source.id}. Agent: {source.agent_status}. Last connection: {formatEntryDate(source.agent_seen_at)}.</p>
    <p>Schedule: {source.schedule_enabled ? "enabled" : "paused"}. Next check: {formatEntryDate(source.next_due_at)}. {source.schedule_error}</p>
    <p>Last check: {formatEntryDate(source.last_checked_at)}. Last success: {formatEntryDate(source.last_success_at)}.</p>
    <CollectionRecovery source={source} allowed={allowed} />
    <p>Rotation offset: {source.rotation_offset}. Deferred threads: {source.deferred}. Failed threads: {source.failed}.</p>
    {source.job && <p>Job #{source.job.id}: {source.job.status}. Attempts: {source.job.attempts}. {source.job.error_code}
      {source.job.retry_at && ` Next retry: ${formatEntryDate(source.job.retry_at)}.`}</p>}
    <form onSubmit={event => { event.preventDefault(); change(`${base}/schedule`, { enabled: true, interval_seconds: Number(interval) }, "PATCH"); }}>
      <label>Interval in seconds for device {source.id}<input type="number" required min="60" max="604800" step="1"
        value={interval} onChange={e => setInterval(e.target.value)} /></label>
      <button disabled={pending || !allowed}>Enable or update device schedule</button>
      <button type="button" disabled={pending} onClick={() => change(`${base}/schedule`, { enabled: false, interval_seconds: source.interval_seconds }, "PATCH")}>Pause device schedule</button>
    </form>
    <button disabled={pending || !allowed || Boolean(active)} onClick={() => change(`${base}/collect-now`, { request_id: crypto.randomUUID() })}>Collect device now</button>
    {active && <button disabled={pending} onClick={() => change(`${base}/cancel`, {})}>Cancel device collection</button>}
    {source.job?.status === "failed" && source.job.error_code !== "SOURCE_DEFERRED" &&
      <button disabled={pending || !allowed} onClick={() => change(`${base}/retry`, {})}>Retry failed device job</button>}
    <Selection key={source.revision} source={source} disabled={pending} save={config => change(`/codex-subscriptions/${source.id}/selection`, { config }, "PATCH")} />
    <button onClick={download}>Download agent settings</button>
    <p>Issuing a token replaces previous tokens and pauses collection. The new secret is displayed once; it is never included in settings downloads.</p>
    <button disabled={pending} onClick={() => change(`/codex-subscriptions/${source.id}/credentials`, { expires_in_days: 30 })}>Issue or rotate device token</button>
    {source.credentials.map(credential => <p key={credential.id}>Token #{credential.id}: expires {formatEntryDate(credential.expires_at)}.
      {credential.revoked_at ? " Revoked." : <button disabled={pending} onClick={() => change(`/codex-subscriptions/${source.id}/credentials/${credential.id}`, {}, "DELETE")}>Revoke token #{credential.id}</button>}</p>)}
    <button disabled={pending} onClick={() => change(`/codex-subscriptions/${source.id}/disconnect`, {})}>Disconnect device</button>
    <p>Start the selected Mac agent explicitly. While offline, collect-now stays pending. Rotation progress does not prove complete history or AI indexing.</p>
  </article>;
}

export default function CodexCollection({ policies }: { policies: Policy[] }) {
  const cache = useQueryClient();
  const [device, setDevice] = useState("");
  const [cwd, setCwd] = useState("");
  const [threads, setThreads] = useState("");
  const [apiUrl, setApiUrl] = useState("http://localhost:8000");
  const [secret, setSecret] = useState<{ source: number; token: string } | null>(null);
  const query = useQuery({ queryKey: ["codex-subscriptions"], queryFn: () => historyRequest<Source[]>("/codex-subscriptions"), refetchInterval: 5000 });
  const mutation = useMutation({
    gcTime: 0,
    mutationFn: async ({ path, data, method = "POST" }: { path: string; data: unknown; method?: "POST" | "PATCH" | "DELETE" }) => {
      setSecret(null);
      const result = await historyRequest<components["schemas"]["CredentialIssued"] | undefined>(path, data, method);
      if (path.endsWith("/credentials") && result) setSecret({ source: Number(path.split("/")[2]), token: result.token });
      // Keep the one-time secret out of the query/mutation caches and persistent storage.
    },
    onSuccess: async () => { await Promise.all([
      cache.invalidateQueries({ queryKey: ["codex-subscriptions"] }), cache.invalidateQueries({ queryKey: ["sources"] }),
      cache.invalidateQueries({ queryKey: ["collection-runs"] }),
    ]); },
  });
  const change = (path: string, data: unknown, method?: "POST" | "PATCH" | "DELETE") => mutation.mutate({ path, data, method });
  return <section aria-label="Codex device collection">
    <h3>Codex device collection</h3>
    <p>Register one stable device UUID and selected local CWD roots or thread IDs, one per line. Reuse the existing UUID for a previously imported Mac. Registration reads no files and starts no agent. AI permission remains separate.</p>
    <form onSubmit={event => { event.preventDefault(); change("/codex-subscriptions", { config: {
      device_uuid: device, include_cwd: lines(cwd), threads: lines(threads),
    } }); }}>
      <label>Device UUID<input required value={device} onChange={e => setDevice(e.target.value)} /></label>
      <button type="button" onClick={() => setDevice(crypto.randomUUID())}>Generate UUID for a new device</button>
      <label>Selected CWD roots (one per line)<textarea value={cwd} onChange={e => setCwd(e.target.value)} /></label>
      <label>Selected thread IDs (one per line)<textarea value={threads} onChange={e => setThreads(e.target.value)} /></label>
      <button disabled={mutation.isPending}>Register Codex device</button>
    </form>
    <label>Agent API address<input value={apiUrl} onChange={e => setApiUrl(e.target.value)} /></label>
    {secret && <div role="status"><p>One-time collector token for subscription {secret.source}. Copy it now and keep it private.</p>
      <textarea aria-label="One-time collector token" readOnly value={secret.token} />
      <button onClick={() => setSecret(null)}>Hide collector token</button></div>}
    {query.isLoading && <p role="status">Loading Codex devices...</p>}
    {query.data?.map(source => <Device key={`${source.id}-${source.interval_seconds}`} source={source} pending={mutation.isPending}
      allowed={policies.find(policy => policy.provider === "codex" && policy.scope === source.scope)?.collection_enabled}
      change={change} download={() => {
        const url = URL.createObjectURL(new Blob([JSON.stringify({ api_url: apiUrl, subscription_id: source.id, source: source.config }, null, 2)], { type: "application/json" }));
        const link = document.createElement("a"); link.href = url; link.download = `codex-device-${source.id}.json`; link.click(); URL.revokeObjectURL(url);
      }} />)}
    {[query.error, mutation.error].filter(Boolean).map((error, index) => <p key={index} role="alert">{error!.message}</p>)}
    {query.error && <button onClick={() => void query.refetch()}>Retry loading Codex devices</button>}
  </section>;
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { historyRequest } from "../api/history";
import type { Policy } from "../api/history";
import type { components } from "../api/generated/schema";
import { formatEntryDate } from "../utils/entries";
import CollectionRecovery from "./CollectionRecovery";

type Subscription = components["schemas"]["SubscriptionResponse"];

function ScheduleControls({ sub, disabled, update }: { sub: Subscription; disabled: boolean;
  update: (enabled: boolean, interval: number) => void }) {
  const [interval, setInterval] = useState(String(sub.interval_seconds));
  return <form onSubmit={event => { event.preventDefault(); update(true, Number(interval)); }}>
    <label>Schedule interval in seconds for {sub.scope}<input type="number" min="60" max="604800"
      step="1" required value={interval} onChange={e => setInterval(e.target.value)} /></label>
    <button disabled={disabled} type="submit">{sub.schedule_enabled ? "Update schedule" : "Enable schedule"}</button>
    <button type="button" disabled={disabled} onClick={() => update(false, sub.interval_seconds)}>Pause schedule</button>
  </form>;
}

function DiscussionControls({ sub, disabled, update }: { sub: Subscription; disabled: boolean;
  update: (enabled: boolean, excluded: number[]) => void }) {
  const [enabled, setEnabled] = useState(sub.discussion_selection.enabled);
  const [excluded, setExcluded] = useState(sub.discussion_selection.exclude_numbers.join(","));
  return <form onSubmit={event => {
    event.preventDefault();
    const values = excluded.trim() ? excluded.split(",").map(value => Number(value.trim())) : [];
    if (values.some(value => !Number.isSafeInteger(value) || value < 1)) return;
    update(enabled, values);
  }}>
    <label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Collect PRs, issues, comments and reviews for {sub.scope}</label>
    <label>Excluded PR/issue numbers for {sub.scope}<input pattern="[0-9, ]*" value={excluded} onChange={e => setExcluded(e.target.value)} /></label>
    <p>Changing this selection pauses the schedule and cancels current work. Archived records remain.</p>
    <button disabled={disabled} type="submit">Save discussion selection</button>
  </form>;
}

export default function GitHubCollection({ policies }: { policies: Policy[] }) {
  const cache = useQueryClient();
  const [repository, setRepository] = useState("");
  const [repositoryId, setRepositoryId] = useState("");
  const [branches, setBranches] = useState("main");
  const [documents, setDocuments] = useState("README.md,ROADMAP.md,DECISIONS.md,docs/**/*.md");
  const [excludePaths, setExcludePaths] = useState("");
  const subscriptions = useQuery({ queryKey: ["collection-subscriptions"],
    queryFn: () => historyRequest<Subscription[]>("/collection-subscriptions"), refetchInterval: 5000 });
  const change = useMutation({
    mutationFn: ({ path, data, method = "POST" }: { path: string; data: unknown; method?: "POST" | "PATCH" }) => historyRequest(path, data, method),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["collection-subscriptions"] });
      await cache.invalidateQueries({ queryKey: ["collection-runs"] });
      await cache.invalidateQueries({ queryKey: ["sources"] });
    },
  });
  const patterns = (value: string) => value.split(",").map(p => p.trim()).filter(Boolean);
  return <section aria-label="GitHub collect now">
    <h3>GitHub collect now</h3>
    <p>Register an exact repository and selected branches/documents. Registration makes no provider request. Schedules need an explicitly started polling worker; stopping it leaves jobs pending until restart. New work collects bounded changes across cycles. Discussion collection requires a separate selection. AI permission stays separate.</p>
    <form onSubmit={event => {
      event.preventDefault();
      change.mutate({ path: "/collection-subscriptions", data: { config: {
        repository, repository_id: Number(repositoryId), branches: patterns(branches),
        documents: patterns(documents), exclude_paths: patterns(excludePaths),
      } } });
    }}>
      <label>Repository (owner/name)<input required value={repository} onChange={e => setRepository(e.target.value)} /></label>
      <label>Repository ID<input required type="number" min="1" step="1" value={repositoryId} onChange={e => setRepositoryId(e.target.value)} /></label>
      <label>Branches (comma separated)<input required value={branches} onChange={e => setBranches(e.target.value)} /></label>
      <label>Document patterns (comma separated)<input value={documents} onChange={e => setDocuments(e.target.value)} /></label>
      <label>Excluded paths (comma separated)<input value={excludePaths} onChange={e => setExcludePaths(e.target.value)} /></label>
      <button disabled={change.isPending} type="submit">Register GitHub source</button>
    </form>
    {subscriptions.isLoading && <p role="status">Loading collect-now sources...</p>}
    {subscriptions.data?.map(sub => {
      const allowed = policies.find(p => p.provider === sub.provider && p.scope === sub.scope)?.collection_enabled;
      const active = sub.job && ["pending", "running"].includes(sub.job.status);
      return <article key={sub.id}>
        <h4>{sub.config.repository} · {sub.scope}</h4>
        <p>Subscription ID: {sub.id}</p>
        <DiscussionControls key={`${sub.id}-${sub.revision}`} sub={sub} disabled={change.isPending}
          update={(enabled, excluded) => change.mutate({ path: `/collection-subscriptions/${sub.id}/discussions`,
            method: "PATCH", data: { enabled, exclude_numbers: excluded } })} />
        <p>Selected branches: {sub.config.branches?.join(", ")}. Schedule: {sub.schedule_enabled ? "enabled" : "paused"}.</p>
        <p>Next scheduled check: {formatEntryDate(sub.next_due_at)}. {sub.schedule_error}</p>
        <ScheduleControls key={`${sub.id}-${sub.interval_seconds}`} sub={sub} disabled={change.isPending || !allowed}
          update={(enabled, interval) => change.mutate({ path: `/collection-subscriptions/${sub.id}/schedule`,
            method: "PATCH", data: { enabled, interval_seconds: interval } })} />
        <p>Last check: {formatEntryDate(sub.last_checked_at)} · Last success: {formatEntryDate(sub.last_success_at)}</p>
        <CollectionRecovery source={sub} allowed={allowed} />
        {Object.entries(sub.incremental.branches).map(([name, branch]) => <p key={name}>
          {name}: observed {branch.observed_head?.slice(0, 10) ?? "unknown"}, graph completed {branch.completed_head?.slice(0, 10) ?? "pending"},
          documents checked {branch.documents_head?.slice(0, 10) ?? "pending"}, pending steps {branch.pending_steps}.
        </p>)}
        <p>Discussion inventory: {sub.incremental.known_threads} known, {sub.incremental.unchecked_threads} unchecked,
          {" "}{sub.incremental.pending_threads} with pages pending. Inventory page: {sub.incremental.inventory_page}.
          Last inventory pass: {formatEntryDate(sub.incremental.inventory_completed_at)}.
          Oldest thread check: {formatEntryDate(sub.incremental.oldest_thread_check)}.</p>
        <p>Last success describes one bounded cycle. Pending history and thread checks may remain; unavailable sources do not erase archived records.</p>
        {sub.job && <p>Job #{sub.job.id}: {sub.job.status}. Attempts: {sub.job.attempts}. {sub.job.run_id && `Batch #${sub.job.run_id}.`} {sub.job.error_code}
          {sub.job.retry_at && ` Next retry: ${formatEntryDate(sub.job.retry_at)}.`}</p>}
        {sub.job?.status === "failed" && <button disabled={change.isPending || !allowed} onClick={() => change.mutate({
          path: `/collection-subscriptions/${sub.id}/retry`, data: {},
        })}>Retry failed job</button>}
        <button disabled={change.isPending || !allowed || Boolean(active)} onClick={() => change.mutate({
          path: `/collection-subscriptions/${sub.id}/collect-now`, data: { request_id: crypto.randomUUID() },
        })}>Collect now</button>
        {active && <button disabled={change.isPending} onClick={() => change.mutate({ path: `/collection-subscriptions/${sub.id}/cancel`, data: {} })}>Cancel collection</button>}
        <p>Historical coverage and batch receipts are below. Collection success does not imply indexing or answer quality.</p>
      </article>;
    })}
    {[subscriptions.error, change.error].filter(Boolean).map((error, i) => <p key={i} role="alert">{error!.message}</p>)}
    {subscriptions.error && <button onClick={() => void subscriptions.refetch()}>Retry collect-now sources</button>}
  </section>;
}

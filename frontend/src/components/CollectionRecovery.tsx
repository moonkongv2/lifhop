import { useEffect, useState } from "react";
import type { components } from "../api/generated/schema";
import { formatEntryDate } from "../utils/entries";

type Source = components["schemas"]["SubscriptionResponse"] | components["schemas"]["CodexSubscriptionResponse"];

const recovery: Record<string, string> = {
  AUTH_FAILED: "Check repository access and the GitHub worker credential, then retry the failed job. Resume the schedule separately.",
  CREDENTIAL_EXPIRED: "Issue a replacement device token, save it with the agent's set-token command, then collect again. Resume the schedule separately.",
  CREDENTIAL_REVOKED: "The device is disconnected. Issue a replacement token and save it with set-token before collecting again.",
  CREDENTIAL_ROTATED: "Save the newly issued token with the agent's set-token command before collecting again. Resume the schedule separately.",
  CONFIG_CHANGED: "Review the new selection before collecting again. For Codex, download updated settings and approve them locally with a new token and spool.",
  MANUAL_BACKFILL_ACTIVE: "Finish or cancel the active manual history import before collecting this source. The enabled schedule will check again later.",
  PARTIAL_COLLECTION: "Inspect the collection batch gaps and blocked or failed receipts below. Resolve the cause, then collect again; resume scheduling separately.",
  SOURCE_DEFERRED: "Some threads are active or changing. Leave the agent running for a later scheduled cycle, or collect again after they become idle.",
  SOURCE_LIMIT: "The selected source exceeds a collection bound. Review the batch gaps and narrow the selection before collecting again.",
  SPOOL_QUOTA: "The private spool reached its size limit. Preserve unfinished recovery data and review local disk usage before retrying.",
  SOURCE_CONFLICT: "Check that the source selection and private spool match. Preserve frozen recovery data; do not overwrite it to force a retry.",
  FORMAT_UNSUPPORTED: "Check the supported local Codex version and format before retrying. Retained records remain available.",
  RETRY_EXHAUSTED: "Automatic attempts have stopped. Check the job error and worker or agent, then retry the failed job. Resume scheduling separately.",
  RATE_LIMIT: "The provider requested a delay. Keep the selected worker running; it can retry at the displayed retry time.",
  TIMEOUT: "A collection attempt timed out. Check connectivity and keep the selected worker or agent running for the bounded retry.",
  READ_FAILED: "The source could not be read. Check access and connectivity; keep the selected worker or agent running for the bounded retry.",
};

export default function CollectionRecovery({ source, allowed }: { source: Source; allowed: boolean | undefined }) {
  const job = source.job;
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => {
    if (job?.status !== "running" || !job.lease_until) return;
    const timer = window.setInterval(() => setClock(Date.now()), 5000);
    return () => window.clearInterval(timer);
  }, [job?.status, job?.lease_until]);
  const deadline = job?.lease_until ? Date.parse(job.lease_until) : Infinity;
  const expired = job?.status === "running" && deadline <= clock;
  const active = job && ["pending", "running"].includes(job.status);
  const code = active ? job.error_code : source.schedule_error || job?.error_code;
  const status = allowed === undefined ? "Collection permission unavailable"
    : !allowed ? "Collection disabled"
    : job?.status === "pending" ? job.retry_at ? "Retry scheduled" : "Queued"
    : job?.status === "running" ? expired ? "Reported lease expired — check worker" : "Collecting"
    : job?.status === "partial" ? "Partially collected"
    : job?.status === "failed" ? "Collection failed"
    : source.schedule_error ? "Needs attention"
    : source.schedule_enabled ? "Scheduled" : "Schedule paused";
  const worker = source.provider === "codex" ? "selected Mac agent" : "selected GitHub polling worker";
  let action = allowed === undefined ? "Wait for source policies to load, or retry loading policies if the request failed."
    : !allowed ? "Enable Allow collection for this source before collecting. AI permission is separate."
    : expired ? `Check or restart the ${worker} with its existing private settings and spool. The next claim can recover this job within its attempt limit. Do not clear recovery data or create a duplicate job.`
    : code && recovery[code] ? recovery[code]
    : job?.status === "cancelled" ? "Cancelled work will not resume. Collect again for a new job, or explicitly enable the schedule."
    : job?.status === "partial" ? recovery.PARTIAL_COLLECTION
    : job?.status === "failed" ? "Inspect the job error and collection batch gaps. Resolve the cause before retrying the failed job. Resume scheduling separately."
    : active ? `Keep the ${worker} running. Committed receipts are reused after reconnect; a replacement worker may need to wait for the previous lease to expire.`
    : source.schedule_enabled ? `Keep the ${worker} running for the next scheduled check.`
    : "Collect now for a single job, or enable the schedule and start the selected worker or agent.";
  if (allowed && job?.status === "failed" && ["RATE_LIMIT", "TIMEOUT", "READ_FAILED"].includes(code ?? "")) {
    action = recovery.RETRY_EXHAUSTED;
  }
  return <div aria-label={`Collection recovery for ${source.scope}`}>
    <p>Collection status: {status}.</p>
    {job?.status === "running" && job.lease_until && <p>Worker lease until: {formatEntryDate(job.lease_until)}.
      {expired && " The last reported lease has expired at this browser's clock. This does not prove the process has stopped; refresh source status and let the server decide whether another attempt can claim the job."}</p>}
    {"agent_status" in source && source.agent_status === "offline" &&
      <p>Device offline: no recent agent contact. Start the selected Mac agent with its existing private settings and spool. An offline device does not mean collection failed.</p>}
    {job?.retry_at && <p>Retry eligible from: {formatEntryDate(job.retry_at)}. A running worker or agent is required.</p>}
    {code && <p>Reason: {code}.</p>}
    <p>Next action: {action}</p>
  </div>;
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router";
import type { Entry } from "../api/entries";
import type { components } from "../api/generated/schema";
import { historyRequest } from "../api/history";
import { entryTarget, resolveEntryContext } from "../utils/entryNavigation";

export default function GitHubReader({ entry }: { entry: Entry }) {
  const cache = useQueryClient();
  const location = useLocation();
  const context = resolveEntryContext(location.search, location.state);
  const query = useQuery({ queryKey: ["github-presentation", entry.id, entry.current_version_id],
    queryFn: () => historyRequest<components["schemas"]["GitHubPresentation"]>(`/entries/${entry.id}/github-presentation`) });
  if (query.isLoading) return <p role="status">Loading GitHub evidence...</p>;
  if (query.error) return <><p role="alert">{query.error.message}</p><button onClick={() => void query.refetch()}>Retry GitHub evidence</button></>;
  const data = query.data;
  if (!data) return null;
  if (data.version_id !== entry.current_version_id) return <><p role="status">The current version changed. Reload this record.</p><button onClick={() => { void cache.invalidateQueries({ queryKey: ["entry", String(entry.id)] }); void query.refetch(); }}>Reload record</button></>;
  const payload = data.payload;
  if (!payload) return <pre className="entry-content reader-body">{entry.content ?? "No content"}</pre>;
  // Require the expected origin even when a response is served from a stale cache.
  const safeLocator = data.locator?.startsWith("https://github.com/") ? data.locator : null;
  return <div className="github-reader">
    <p>Repository: {payload.repository} · Commit: <code>{payload.sha}</code></p>
    {safeLocator && <p><a href={safeLocator} target="_blank" rel="noopener noreferrer">Open GitHub source</a></p>}
    {!!payload.omissions?.length && <p className="help-text">Collection gaps: {payload.omissions.join(", ")}</p>}
    {payload.kind === "github_commit" ? <>
      <h3>Commit message</h3><pre className="entry-content">{payload.message}</pre>
      <p>Author: {payload.author?.name || "Unknown"} · Author date: {payload.author?.date || "Unavailable"}<br />Committer: {payload.committer?.name || "Unknown"} · Commit date: {payload.committer?.date || "Unavailable"}</p>
      <p>Parents: {payload.parents?.join(", ") || "Root commit"}</p>
      <h3>Recorded file changes</h3>
      <p className="help-text">Diffs are stored evidence. Commands and imported HTML are displayed as text.</p>
      {payload.files?.map(file => <details key={file.path}><summary>{file.status} · {file.path} · +{file.additions} / −{file.deletions} · {file.patch_state}</summary>
        {file.previous_path && <p>Previous path: {file.previous_path}</p>}
        <pre className="entry-content">{file.patch ?? "Patch unavailable from the source."}</pre>
      </details>)}
    </> : <>
      <h3>Document snapshot · {payload.path}</h3>
      <p className="help-text">Content at the recorded commit. {payload.snapshot_reason === "head_baseline" ? "Selected-head baseline; the last edit date is unknown." : "Captured from a document change at this commit."} This is a historical snapshot.</p>
      <p>Blob: <code>{payload.blob_sha}</code></p>
      <pre className="entry-content reader-body">{payload.content}</pre>
    </>}
    {!!data.related.length && <><h3>Records from this commit</h3><ul>{data.related.map(record => <li key={record.id}><Link to={entryTarget(record.id, context)}>{record.title}</Link></li>)}</ul></>}
    {data.related_has_more && <p>More related records are available through Search.</p>}
  </div>;
}

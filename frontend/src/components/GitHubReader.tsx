import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router";
import type { Entry } from "../api/entries";
import type { components } from "../api/generated/schema";
import { historyRequest } from "../api/history";
import { entryTarget, resolveEntryContext } from "../utils/entryNavigation";
import { githubEntryTarget, safeRepositoryContext, discussionTarget, repositoryTarget } from "../utils/githubRepositories";

export default function GitHubReader({ entry }: { entry: Entry }) {
  const cache = useQueryClient();
  const location = useLocation();
  const context = resolveEntryContext(location.search, location.state);
  const repository = safeRepositoryContext(new URLSearchParams(location.search).get("repositoryReturn"));
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
  if (payload.kind !== "github_commit" && payload.kind !== "github_document") {
    const parentKind = "parent_kind" in payload ? payload.parent_kind : payload.kind === "github_pull_request" ? "pull_request" : "issue";
    const parentId = "parent_id" in payload ? payload.parent_id : payload.object_id;
    return <div className="github-reader">
      {entry.source_state === "deleted" && <span className="badge">Deleted at source</span>}
      {entry.review_required && <span className="badge">Version review needed</span>}
      <p>Repository: {payload.repository} · {parentKind === "pull_request" ? "PR" : "Issue"} #{payload.number}</p>
      {safeLocator && <p><a href={safeLocator} target="_blank" rel="noopener noreferrer">Open GitHub source</a></p>}
      <p><Link to={repository?.tab === "discussions" && repository.thread_kind === parentKind && repository.thread_id === String(parentId)
        ? repositoryTarget({...repository,focus_entry_id:entry.id})
        : discussionTarget(`repo:${payload.repository_id}`,parentKind,String(parentId),context,entry.id)}>Browse discussion</Link></p>
      {"state" in payload && <p>State: {payload.state}{payload.kind === "github_pull_request" && payload.merged ? " · Merged" : ""}{payload.kind === "github_pull_request" && payload.draft ? " · Draft" : ""}</p>}
      <p>Author: {payload.author ?? "Unknown"}</p>
      {payload.kind === "github_review" && <p className="help-text">{payload.state === "PENDING" ? "Unsubmitted draft review. " : ""}Changes without a verified edit date need explicit version selection.</p>}
      {!!payload.omissions.length && <p className="help-text">Collection gaps: {payload.omissions.join(", ")}</p>}
      <pre className="entry-content reader-body">{payload.body || (payload.body_state === "unavailable" ? "Body unavailable" : "Empty body")}</pre>
      {payload.kind === "github_review_comment" && <>
        <p>Code location: {payload.path ?? "Unavailable"}:{payload.line ?? "unknown"} ({payload.side ?? "side unknown"})
          {payload.original_line && ` · Original line: ${payload.original_line}`}</p>
        {payload.review_id && <p>Review ID: {payload.review_id}</p>}{payload.in_reply_to_id && <p>Reply to code comment ID: {payload.in_reply_to_id}</p>}
        {payload.diff_hunk && <details><summary>Recorded code context</summary><pre className="entry-content">{payload.diff_hunk}</pre></details>}
      </>}
      {payload.kind === "github_pull_request" && !payload.commits_complete && <p className="help-text">PR commit membership is incomplete.</p>}
      {!!data.commit_links?.length && <details><summary>Related commits</summary><ul>{data.commit_links.map(link=><li key={link.sha}>
        {link.roles.join(", ")} · {link.entry_id ? <Link to={repository ? githubEntryTarget(link.entry_id,repository) : entryTarget(link.entry_id,context)}>{link.sha.slice(0,8)}</Link>
          : <a href={`https://github.com/${payload.repository}/commit/${link.sha}`} target="_blank" rel="noopener noreferrer">{link.sha.slice(0,8)} · Not retained locally</a>}
      </li>)}</ul></details>}
    </div>;
  }
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
    {!!data.related.length && <><h3>Records from this commit</h3><ul>{data.related.map(record => <li key={record.id}><Link to={repository ? githubEntryTarget(record.id,repository) : entryTarget(record.id, context)}>{record.title}</Link></li>)}</ul></>}
    {data.related_has_more && <p>More related records are available through Search.</p>}
  </div>;
}

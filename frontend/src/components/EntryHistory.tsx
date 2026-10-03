import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchVersions, chooseVersion, saveSettings, saveSourceState } from "../api/history";
import type { Entry } from "../api/entries";
import { formatEntryDate } from "../utils/entries";
import Icon from "./Icon";
import ArtifactDownload from "./ArtifactDownload";

export default function EntryHistory({ entry }: { entry: Entry }) {
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const [annotation, setAnnotation] = useState(entry.annotation ?? "");
  const [selected, setSelected] = useState<number | null>(null);
  const versions = useQuery({ queryKey: ["entry-versions", entry.id], queryFn: () => fetchVersions(entry.id), enabled: open });
  const change = useMutation({
    mutationFn: (action: { kind: "select" | "annotation" | "ai" | "state"; value?: string | number | boolean }) => {
      if (action.kind === "select") return chooseVersion(entry.id, action.value as number);
      if (action.kind === "state") return saveSourceState(entry.id, action.value as string);
      return saveSettings(entry.id, action.kind === "ai" ? { external_ai_allowed: action.value as boolean } : { annotation });
    },
    onSuccess: async (saved) => {
      cache.setQueryData(["entry", String(entry.id)], saved);
      await cache.invalidateQueries({ queryKey: ["entries"] });
      await cache.invalidateQueries({ queryKey: ["entry-versions", entry.id] });
    },
  });
  const version = versions.data?.find(v => v.id === selected);
  return <aside className="panel notes-panel" aria-label="Notes and history">
    <div className="panel-heading"><Icon name="note" /><h3>Notes & history</h3></div>
    {entry.read_only && <p>Imported source content is read-only. Write your own notes below.</p>}
    <p>Source status: <strong>{entry.source_state ?? "unknown"}</strong>. Source deletions remain in local search; deleting in lifhop removes all versions.</p>
    {entry.review_required && <p className="review-notice" role="status">A snapshot needs review. Current content was kept because freshness or completeness could not be established.</p>}
    <label htmlFor="annotation">Personal annotation</label>
    <textarea id="annotation" placeholder="Keep your own thoughts alongside the source…" value={annotation} maxLength={100000} onChange={e => setAnnotation(e.target.value)} />
    <button className="primary save-note" disabled={change.isPending} onClick={() => change.mutate({ kind: "annotation" })}>Save annotation</button>
    <p><button className="history-toggle" aria-expanded={open} onClick={() => setOpen(!open)}><Icon name="history" />{open ? "Hide history" : "View history and provenance"}</button></p>
    {open && <div className="history-list">
      {versions.isLoading && <p role="status">Loading history...</p>}
      {versions.error && <><p role="alert">{versions.error.message}</p><button onClick={() => void versions.refetch()}>Retry history</button></>}
      {versions.data?.map(v => <article key={v.id}>
        <h4>Version {v.number} {v.id === entry.current_version_id ? "— Current" : "— Retained"}</h4>
        <p>{v.title} · {v.completeness} · {v.material_kind}</p>
        <p>Observed: {formatEntryDate(v.observed_at)} · Source modified: {formatEntryDate(v.source_updated_at)}</p>
        <p>Parser: {v.parser_version}</p>
        <button onClick={() => setSelected(selected === v.id ? null : v.id)}>Inspect version {v.number}</button>
        {v.id !== entry.current_version_id && <button disabled={change.isPending} onClick={() => {
          if (window.confirm(`Use version ${v.number} as current? Completeness: ${v.completeness}. Existing history will be retained.`)) change.mutate({ kind: "select", value: v.id });
        }}>Use as current</button>}
      </article>)}
      {version && <section className="version-preview"><h4>Version {version.number}: provenance and content</h4>
        <p>Provider: {entry.provider ?? "unknown"} · Identity: {entry.external_id ?? "not recorded"} · Scope: {entry.source_scope}</p>
        <p>Locator: {version.locator ?? "Not recorded"}</p>
        <p>SHA-256: <code>{version.content_hash}</code></p>
        {version.payload?.kind === "dev_session" && <>
          <p>Thread: {String(version.payload.thread_id ?? "Not recorded")}<br />Turn: {String(version.payload.turn_id ?? "Not recorded")}</p>
          {typeof version.payload.forked_from_id === "string" && <p>Forked from: {version.payload.forked_from_id}</p>}
          {version.payload.archived === true && <p>Read from archived history.</p>}
          {Array.isArray(version.payload.omissions) && version.payload.omissions.length > 0 && <div className="review-notice">
            <h4>Collection gaps</h4><ul>{version.payload.omissions.filter((code): code is string => typeof code === "string").map(code => <li key={code}>{code.replaceAll("_", " ").toLowerCase()}</li>)}</ul>
          </div>}
        </>}
        <pre className="entry-content">{version.content ?? "No content"}</pre>
        {version.payload && <details><summary>Structured messages, commands and diffs</summary><pre className="entry-content">{JSON.stringify(version.payload, null, 2)}</pre></details>}
        {version.import_artifact_id && <ArtifactDownload artifactId={version.import_artifact_id} />}
      </section>}
    </div>}
    <details className="policy-details"><summary>Source status and AI permission</summary>
      <p>External AI needs both source and record permission. New sources and records start disabled. No AI service is connected yet.</p>
      <label><input type="checkbox" checked={entry.external_ai_allowed ?? false} disabled={change.isPending}
        onChange={e => change.mutate({ kind: "ai", value: e.target.checked })} />Allow external AI for this record</label>
      <p>Only mark a source deletion after checking the source yourself.</p>
      <div className="actions">{["available", "unavailable", "unknown", "deleted"].map(state =>
        <button key={state} disabled={change.isPending || entry.source_state === state} onClick={() => {
          if (state !== "deleted" || window.confirm("Have you confirmed that this record was deleted at its source?")) change.mutate({ kind: "state", value: state });
        }}>Mark {state === "deleted" ? "confirmed source deletion" : state}</button>)}</div>
    </details>
    {change.error && <p role="alert">{change.error.message}</p>}
    {change.isSuccess && <p role="status">Saved.</p>}
  </aside>;
}

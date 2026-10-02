import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useParams, useLocation } from "react-router";
import { deleteEntry, fetchEntry, updateEntry } from "../api/entries";
import type { EntryUpdate } from "../api/entries";
import Icon from "../components/Icon";
import RecordSidebar from "../components/RecordSidebar";
import EntryHistory from "../components/EntryHistory";
import ArtifactDownload from "../components/ArtifactDownload";
import { formatEntryDate, sourceLabels } from "../utils/entries";
import EntryForm from "../components/EntryForm";
import { listTarget, resolveEntryContext } from "../utils/entryNavigation";

function EntryDetail() {
  const { id } = useParams();
  const location = useLocation();
  const context = resolveEntryContext(location.search, location.state);
  const returnTarget = listTarget(context);
  const backLabel = context.pathname === "/search" ? "Back to search" : "Back to entries";
  const token = localStorage.getItem("access_token");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { data: entry, isLoading, error, refetch } = useQuery({
    queryKey: ["entry", id],
    queryFn: () => fetchEntry(id!),
    enabled: Boolean(token && id),
  });
  const save = useMutation({
    mutationFn: (data: EntryUpdate) => updateEntry(id!, data),
    onSuccess: async (saved) => {
      queryClient.setQueryData(["entry", id], saved);
      await queryClient.invalidateQueries({ queryKey: ["entries"] });
      setEditing(false);
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteEntry(id!),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ["entry", id], exact: true });
      queryClient.removeQueries({ queryKey: ["entry-versions", Number(id)] });
      await queryClient.invalidateQueries({ queryKey: ["suppressed"] });
      await queryClient.invalidateQueries({ queryKey: ["purges"] });
      await queryClient.invalidateQueries({ queryKey: ["entries"] });
      navigate(returnTarget, { replace: true });
    },
  });

  if (!token) return <Navigate to="/login" replace />;
  if (!id) return <p>Entry ID is missing.</p>;
  if (isLoading) return <p role="status">Loading...</p>;
  if (error) return <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>Retry</button><Link to={returnTarget}>{backLabel}</Link></>;
  if (!entry) return <p>Entry not found.</p>;

  return (
    <>
      <Link className="back-link" to={returnTarget}>← {backLabel}</Link>
      <div className="reader-layout">
        <RecordSidebar selectedId={entry.id} context={context} />
        <section className="panel reader-panel" aria-label="Record reader">
          {editing ? (
            <>
              <h2>Edit entry</h2>
              <EntryForm key={entry.id} entry={entry} pending={save.isPending} error={save.error}
                onSubmit={(data) => save.mutate(data)} onCancel={() => { setEditing(false); save.reset(); }} />
            </>
          ) : (
            <>
              <div className="reader-tools">
                <div className="badges"><span className="badge source">{sourceLabels[entry.source ?? "unknown"]}</span><span className="badge">{entry.type}</span></div>
                <details className="entry-menu"><summary aria-label="Record actions"><Icon name="more" /></summary><div><button className="danger" onClick={(event) => { setConfirmDelete(true); event.currentTarget.closest("details")?.removeAttribute("open"); }}>Delete</button></div></details>
              </div>
              <h2>{entry.title}</h2>
              <p className="reader-meta">Source/event date: {formatEntryDate(entry.event_at)} (Asia/Seoul)</p>
              {confirmDelete && (
                <div className="delete-confirm">
                  <p>Delete this entry and all versions? Imported records will be blocked from reimport. Associated originals, including shared ZIPs, will be purged.</p>
                  <div className="actions">
                    <button className="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
                      {remove.isPending ? "Deleting..." : "Confirm delete"}
                    </button>
                    <button disabled={remove.isPending} onClick={() => { setConfirmDelete(false); remove.reset(); }}>Cancel</button>
                  </div>
                  {remove.error && <p role="alert">{remove.error.message}</p>}
                </div>
              )}
              <p className="entry-content reader-body">{entry.content ?? "No content"}</p>
              <div className="reader-footer"><p>Added: {formatEntryDate(entry.created_at)} (Asia/Seoul)</p>
              <p>Updated: {formatEntryDate(entry.updated_at)} (Asia/Seoul)</p></div>
              {entry.import_artifact_id && <ArtifactDownload key={entry.import_artifact_id} artifactId={entry.import_artifact_id} />}
              {!entry.read_only && <div className="actions"><button onClick={() => setEditing(true)}><Icon name="note" />Edit</button></div>}
            </>
          )}
        </section>
        <EntryHistory key={entry.id} entry={entry} />
      </div>
    </>
  );
}

export default function EntryDetailPage() {
  const { id } = useParams();
  return <EntryDetail key={id} />;
}

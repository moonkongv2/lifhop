import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useParams, useLocation } from "react-router";
import { deleteEntry, fetchEntry, updateEntry } from "../api/entries";
import type { EntryUpdate } from "../api/entries";
import ArtifactDownload from "../components/ArtifactDownload";
import { formatEntryDate, sourceLabels } from "../utils/entries";
import EntryForm from "../components/EntryForm";

function EntryDetailPage() {
  const { id } = useParams();
  const location = useLocation();
  const search = typeof location.state?.entryListSearch === "string" ? location.state.entryListSearch : "";
  const listTarget = search ? `/entries?${search}` : "/entries";
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
      await queryClient.invalidateQueries({ queryKey: ["entries"] });
      navigate(listTarget, { replace: true });
    },
  });

  if (!token) return <Navigate to="/login" replace />;
  if (!id) return <p>Entry ID is missing.</p>;
  if (isLoading) return <p role="status">Loading...</p>;
  if (error) return <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>Retry</button><Link to={listTarget}>Back to entries</Link></>;
  if (!entry) return <p>Entry not found.</p>;

  return (
    <>
      <Link to={listTarget}>← Back to entries</Link>
      {editing ? (
        <>
          <h2>Edit entry</h2>
          <EntryForm key={entry.id} entry={entry} pending={save.isPending} error={save.error}
            onSubmit={(data) => save.mutate(data)} onCancel={() => { setEditing(false); save.reset(); }} />
        </>
      ) : (
        <>
          <h2>{entry.title}</h2>
          <p>{sourceLabels[entry.source ?? "unknown"]} · {entry.type}</p>
          <p className="entry-content">{entry.content ?? "No content"}</p>
          <p>Source/event date: {formatEntryDate(entry.event_at)} (Asia/Seoul)</p>
          <p>Added: {formatEntryDate(entry.created_at)} (Asia/Seoul)</p>
          <p>Updated: {formatEntryDate(entry.updated_at)} (Asia/Seoul)</p>
          {entry.import_artifact_id && <ArtifactDownload key={entry.import_artifact_id} artifactId={entry.import_artifact_id} />}
          {confirmDelete ? (
            <div>
              <p>Delete this entry? This action cannot be undone.</p>
              <div className="actions">
                <button disabled={remove.isPending} onClick={() => remove.mutate()}>
                  {remove.isPending ? "Deleting..." : "Confirm delete"}
                </button>
                <button disabled={remove.isPending} onClick={() => { setConfirmDelete(false); remove.reset(); }}>Cancel</button>
              </div>
              {remove.error && <p role="alert">{remove.error.message}</p>}
            </div>
          ) : (
            <div className="actions">
              <button onClick={() => setEditing(true)}>Edit</button>
              <button onClick={() => setConfirmDelete(true)}>Delete</button>
            </div>
          )}
        </>
      )}
    </>
  );
}

export default EntryDetailPage;

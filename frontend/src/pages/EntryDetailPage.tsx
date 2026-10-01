import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { deleteEntry, fetchEntry, updateEntry } from "../api/entries";
import type { EntryUpdate } from "../api/entries";
import ArtifactDownload from "../components/ArtifactDownload";
import EntryForm from "../components/EntryForm";

function EntryDetailPage() {
  const { id } = useParams();
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
      navigate("/entries", { replace: true });
    },
  });

  if (!token) return <Navigate to="/login" replace />;
  if (!id) return <p>Entry ID가 없어.</p>;
  if (isLoading) return <p role="status">불러오는 중...</p>;
  if (error) return <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>다시 시도</button><Link to="/entries">목록으로</Link></>;
  if (!entry) return <p>Entry를 찾을 수 없어.</p>;

  return (
    <>
      <Link to="/entries">← 목록으로</Link>
      {editing ? (
        <>
          <h2>Entry 수정</h2>
          <EntryForm key={entry.id} entry={entry} pending={save.isPending} error={save.error}
            onSubmit={(data) => save.mutate(data)} onCancel={() => { setEditing(false); save.reset(); }} />
        </>
      ) : (
        <>
          <h2>{entry.title}</h2>
          <p>Type: {entry.type}</p>
          <p className="entry-content">{entry.content ?? "내용 없음"}</p>
          {entry.event_at && <p>Event at: {new Date(entry.event_at).toLocaleString()}</p>}
          <p>Created: {new Date(entry.created_at).toLocaleString()}</p>
          <p>Updated: {new Date(entry.updated_at).toLocaleString()}</p>
          {entry.import_artifact_id && <ArtifactDownload key={entry.import_artifact_id} artifactId={entry.import_artifact_id} />}
          {confirmDelete ? (
            <div>
              <p>이 Entry를 삭제할까? 삭제한 기록은 복구할 수 없어.</p>
              <div className="actions">
                <button disabled={remove.isPending} onClick={() => remove.mutate()}>
                  {remove.isPending ? "삭제 중..." : "삭제 확인"}
                </button>
                <button disabled={remove.isPending} onClick={() => { setConfirmDelete(false); remove.reset(); }}>취소</button>
              </div>
              {remove.error && <p role="alert">{remove.error.message}</p>}
            </div>
          ) : (
            <div className="actions">
              <button onClick={() => setEditing(true)}>수정</button>
              <button onClick={() => setConfirmDelete(true)}>삭제</button>
            </div>
          )}
        </>
      )}
    </>
  );
}

export default EntryDetailPage;

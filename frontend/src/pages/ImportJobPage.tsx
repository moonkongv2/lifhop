import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useParams } from "react-router";
import { fetchJob, fetchJobEntries, isActive, retryJob, statusText } from "../api/imports";
import ArtifactDownload from "../components/ArtifactDownload";

function ImportJobPage() {
  const { id } = useParams();
  const [offset, setOffset] = useState(0);
  const queryClient = useQueryClient();
  const token = localStorage.getItem("access_token");
  const job = useQuery({ queryKey: ["import-job", id], queryFn: () => fetchJob(id!), enabled: Boolean(id && token),
    refetchInterval: (query) => query.state.data && isActive(query.state.data) ? 2000 : false,
  });
  const entries = useQuery({ queryKey: ["import-job-entries", id, job.data?.attempts, job.data?.status, offset],
    queryFn: () => fetchJobEntries(id!, offset), enabled: Boolean(token && job.data && !isActive(job.data)),
  });
  const finalStatus = job.data?.status;
  const attempts = job.data?.attempts;
  useEffect(() => {
    if (finalStatus && finalStatus !== "PENDING" && finalStatus !== "RUNNING") {
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["entry"] });
      void queryClient.invalidateQueries({ queryKey: ["import-jobs"] });
    }
  }, [finalStatus, attempts, queryClient]);
  const retry = useMutation({ mutationFn: () => retryJob(id!), onSuccess: async () => {
    setOffset(0);
    await queryClient.invalidateQueries({ queryKey: ["import-job", id] });
    await queryClient.invalidateQueries({ queryKey: ["import-jobs"] });
    await queryClient.invalidateQueries({ queryKey: ["entries"] });
    await queryClient.invalidateQueries({ queryKey: ["entry"] });
  } });

  if (!token) return <Navigate to="/login" replace />;
  if (job.isLoading) return <p role="status">Loading job...</p>;
  if (job.error) return <><p role="alert">{job.error.message}</p><button onClick={() => void job.refetch()}>Retry</button><Link to="/imports">Back to imports</Link></>;
  if (!job.data) return <p>Job not found.</p>;
  const data = job.data;
  return (
    <>
      <Link to="/imports">← Back to imports</Link>
      <h2>Import job #{data.id}</h2>
      <p role="status">{statusText[data.status]}</p>
      <p>Total {data.total_items} / Saved {data.processed_items} / Failed {data.failed_items} / Attempts {data.attempts}</p>
      {isActive(data) && <p>Job status and saved progress update automatically. The total may be 0 while the archive is being validated.</p>}
      {data.error && <p role="alert">{data.error}</p>}
      {data.item_errors.length > 0 && <section><h3>Item errors</h3><ul>
        {data.item_errors.map((error) => <li key={error.index}>Item {error.index}: {error.message} ({error.code})</li>)}
      </ul></section>}
      {(data.status === "FAILED" || data.status === "PARTIAL") && <>
        <p>Interrupted jobs resume from saved progress. If all items were processed but some failed, retry processes the entire ZIP again. To fix an invalid file, upload a corrected ZIP.</p>
        <button disabled={retry.isPending} onClick={() => retry.mutate()}>{retry.isPending ? "Requesting retry..." : "Retry job"}</button>
      </>}
      {retry.error && <p role="alert">{retry.error.message}</p>}
      <ArtifactDownload key={data.artifact_id} artifactId={data.artifact_id} />
      {!isActive(data) && <section><h3>Result entries</h3>
        {entries.isLoading && <p>Loading results...</p>}
        {entries.error && <><p role="alert">{entries.error.message}</p><button onClick={() => void entries.refetch()}>Retry loading results</button></>}
        {entries.data?.length === 0 && <p>No result entries available.</p>}
        {entries.data?.map((entry) => <p key={entry.id}><Link to={`/entries/${entry.id}`}>{entry.title}</Link></p>)}
        <div className="actions"><button disabled={offset === 0} onClick={() => setOffset(offset - 20)}>Previous results</button>
          <button disabled={!entries.data || entries.data.length < 20} onClick={() => setOffset(offset + 20)}>Next results</button></div>
      </section>}
    </>
  );
}
export default ImportJobPage;

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
  if (job.isLoading) return <p role="status">작업을 불러오는 중...</p>;
  if (job.error) return <><p role="alert">{job.error.message}</p><button onClick={() => void job.refetch()}>다시 시도</button><Link to="/imports">가져오기로</Link></>;
  if (!job.data) return <p>작업을 찾을 수 없어.</p>;
  const data = job.data;
  return (
    <>
      <Link to="/imports">← 가져오기로</Link>
      <h2>가져오기 작업 #{data.id}</h2>
      <p role="status">{statusText[data.status]}</p>
      <p>전체 {data.total_items} / 성공 {data.processed_items} / 실패 {data.failed_items} / 시도 {data.attempts}</p>
      {isActive(data) && <p>작업 상태를 자동 확인하고 있어. 처리 중 건수는 완료 후 표시돼. 대기가 계속되면 워커 실행 여부를 확인해 줘.</p>}
      {data.error && <p role="alert">{data.error}</p>}
      {data.item_errors.length > 0 && <section><h3>항목별 오류</h3><ul>
        {data.item_errors.map((error) => <li key={error.index}>항목 {error.index}: {error.message} ({error.code})</li>)}
      </ul></section>}
      {(data.status === "FAILED" || data.status === "PARTIAL") && <>
        <p>재시도는 보관된 같은 ZIP을 다시 처리해. 파일 내용이 잘못됐으면 수정한 ZIP을 새로 올려 줘.</p>
        <button disabled={retry.isPending} onClick={() => retry.mutate()}>{retry.isPending ? "재시도 요청 중..." : "작업 재시도"}</button>
      </>}
      {retry.error && <p role="alert">{retry.error.message}</p>}
      <ArtifactDownload key={data.artifact_id} artifactId={data.artifact_id} />
      {!isActive(data) && <section><h3>결과 기록</h3>
        {entries.isLoading && <p>결과를 불러오는 중...</p>}
        {entries.error && <><p role="alert">{entries.error.message}</p><button onClick={() => void entries.refetch()}>결과 다시 시도</button></>}
        {entries.data?.length === 0 && <p>조회 가능한 결과 기록이 없어.</p>}
        {entries.data?.map((entry) => <p key={entry.id}><Link to={`/entries/${entry.id}`}>{entry.title}</Link></p>)}
        <div className="actions"><button disabled={offset === 0} onClick={() => setOffset(offset - 20)}>이전 결과</button>
          <button disabled={!entries.data || entries.data.length < 20} onClick={() => setOffset(offset + 20)}>다음 결과</button></div>
      </section>}
    </>
  );
}
export default ImportJobPage;

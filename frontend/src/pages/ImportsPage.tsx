import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate } from "react-router";
import { fetchJobs, isActive, statusText, uploadChatGPT, uploadMarkdown } from "../api/imports";
import type { Entry } from "../api/entries";
import ArtifactDownload from "../components/ArtifactDownload";

function ImportsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [kind, setKind] = useState("markdown");
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const jobs = useQuery({ queryKey: ["import-jobs"], queryFn: fetchJobs,
    enabled: Boolean(localStorage.getItem("access_token")),
    refetchInterval: (query) => query.state.data?.some(isActive) ? 2000 : false,
  });
  const upload = useMutation({
    mutationFn: async ({ file, kind }: { file: File; kind: string }) => {
      if (kind === "markdown") return { entries: await uploadMarkdown(file) };
      return { job: await uploadChatGPT(file) };
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["entries"] });
      await queryClient.invalidateQueries({ queryKey: ["import-jobs"] });
      if (result.job) navigate(`/import-jobs/${result.job.job_id}`);
      else setEntries(result.entries ?? []);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (upload.isPending) return;
    if (!file || file.size === 0) { setValidation("내용이 있는 파일을 선택해 줘."); return; }
    const valid = kind === "markdown" ? /\.(md|markdown)$/i.test(file.name) : /\.zip$/i.test(file.name);
    if (!valid) { setValidation("선택한 가져오기 종류에 맞는 파일을 선택해 줘."); return; }
    setValidation("");
    setEntries([]);
    upload.mutate({ file, kind });
  }

  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;
  return (
    <>
      <h2>기록 가져오기</h2>
      <p>Markdown은 UTF-8 텍스트, ChatGPT는 내보내기 ZIP을 선택해 줘.</p>
      <p>기본 한도: Markdown 25 MiB, ZIP 1 GiB, ZIP 내부 전체 1 GiB, 대화 JSON 합계 256 MiB, 대화 2,000개. 분할 대화 JSON도 지원해. 서버 설정에 따라 달라질 수 있어.</p>
      <form onSubmit={submit}>
        <fieldset disabled={upload.isPending}>
          <label htmlFor="import-kind">가져오기 종류</label>
          <select id="import-kind" value={kind} onChange={(event) => { setKind(event.target.value); setFile(null); upload.reset(); setValidation(""); }}>
            <option value="markdown">Markdown</option><option value="chatgpt">ChatGPT ZIP</option>
          </select>
          <label htmlFor="import-file">파일</label>
          <input key={kind} id="import-file" type="file" accept={kind === "markdown" ? ".md,.markdown" : ".zip"}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button type="submit">{upload.isPending ? "업로드 중..." : "가져오기"}</button>
        </fieldset>
      </form>
      {(validation || upload.error) && <p role="alert">{validation || upload.error?.message}</p>}
      {entries.length > 0 && <section><h3>가져오기 완료</h3><p>{entries.length}개 기록을 저장했어.</p>
        {entries.map((entry) => <p key={entry.id}><Link to={`/entries/${entry.id}`}>{entry.title}</Link></p>)}
        {entries[0].import_artifact_id && <ArtifactDownload artifactId={entries[0].import_artifact_id} />}
      </section>}
      <h3>최근 ChatGPT 가져오기 작업</h3>
      {jobs.isLoading && <p role="status">작업 목록을 불러오는 중...</p>}
      {jobs.error && <><p role="alert">{jobs.error.message}</p><button onClick={() => void jobs.refetch()}>작업 목록 다시 시도</button></>}
      {jobs.data?.length === 0 && <p>가져오기 작업이 없어.</p>}
      {jobs.data?.map((job) => <article key={job.id}>
        <Link to={`/import-jobs/${job.id}`}>작업 #{job.id}</Link> — {statusText[job.status]}
        <p>성공 {job.processed_items} / 실패 {job.failed_items} / 전체 {job.total_items}</p>
      </article>)}
    </>
  );
}
export default ImportsPage;

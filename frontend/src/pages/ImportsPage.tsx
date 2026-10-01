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
    if (!file || file.size === 0) { setValidation("Please select a non-empty file."); return; }
    const valid = kind === "markdown" ? /\.(md|markdown)$/i.test(file.name) : /\.zip$/i.test(file.name);
    if (!valid) { setValidation("Please select a file that matches the import type."); return; }
    setValidation("");
    setEntries([]);
    upload.mutate({ file, kind });
  }

  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;
  return (
    <>
      <h2>Import records</h2>
      <p>Choose a UTF-8 text file for Markdown or an export ZIP for ChatGPT.</p>
      <p>Default limits: Markdown 25 MiB, ZIP 1 GiB, total uncompressed archive 1 GiB, conversation JSON 256 MiB, and 2,000 conversations. Split conversation JSON files are supported. Limits may vary with server settings.</p>
      <form onSubmit={submit}>
        <fieldset disabled={upload.isPending}>
          <label htmlFor="import-kind">Import type</label>
          <select id="import-kind" value={kind} onChange={(event) => { setKind(event.target.value); setFile(null); upload.reset(); setValidation(""); }}>
            <option value="markdown">Markdown</option><option value="chatgpt">ChatGPT ZIP</option>
          </select>
          <label htmlFor="import-file">File</label>
          <input key={kind} id="import-file" type="file" accept={kind === "markdown" ? ".md,.markdown" : ".zip"}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button type="submit">{upload.isPending ? "Uploading..." : "Import"}</button>
        </fieldset>
      </form>
      {(validation || upload.error) && <p role="alert">{validation || upload.error?.message}</p>}
      {entries.length > 0 && <section><h3>Import complete</h3><p>{entries.length} {entries.length === 1 ? "entry" : "entries"} saved.</p>
        {entries.map((entry) => <p key={entry.id}><Link to={`/entries/${entry.id}`}>{entry.title}</Link></p>)}
        {entries[0].import_artifact_id && <ArtifactDownload artifactId={entries[0].import_artifact_id} />}
      </section>}
      <h3>Recent ChatGPT import jobs</h3>
      {jobs.isLoading && <p role="status">Loading jobs...</p>}
      {jobs.error && <><p role="alert">{jobs.error.message}</p><button onClick={() => void jobs.refetch()}>Retry loading jobs</button></>}
      {jobs.data?.length === 0 && <p>No import jobs yet.</p>}
      {jobs.data?.map((job) => <article key={job.id}>
        <Link to={`/import-jobs/${job.id}`}>Job #{job.id}</Link> — {statusText[job.status]}
        <p>Saved {job.processed_items} / Failed {job.failed_items} / Total {job.total_items}</p>
      </article>)}
    </>
  );
}
export default ImportsPage;

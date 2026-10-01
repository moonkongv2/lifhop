import type { components } from "./generated/schema";
import type { Entry } from "./entries";

export type ImportJob = components["schemas"]["ImportJobResponse"];
type Submission = components["schemas"]["ImportJobSubmissionResponse"];

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("Please log in to continue.");
  const response = await fetch(`/api${path}`, {
    ...options, headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    let detail: unknown;
    try { detail = (await response.json()).detail; } catch { /* Use the status fallback. */ }
    if (response.status === 401) throw new Error("Your session has expired. Please log in again.");
    throw new Error(typeof detail === "string" ? detail : `Import request failed: ${response.status}. Please try again.`);
  }
  return response.json();
}

export const fetchJobs = () => request<ImportJob[]>("/import-jobs");
export const fetchJob = (id: string) => request<ImportJob>(`/import-jobs/${id}`);
export const fetchJobEntries = (id: string, offset: number) =>
  request<Entry[]>(`/import-jobs/${id}/entries?limit=20&offset=${offset}`);
export const retryJob = (id: string) => request<Submission>(`/import-jobs/${id}/retry`, { method: "POST" });
export async function uploadMarkdown(file: File): Promise<Entry[]> {
  const form = new FormData(); form.append("file", file);
  return request("/imports/markdown", { method: "POST", body: form });
}
export async function uploadChatGPT(file: File): Promise<Submission> {
  const form = new FormData(); form.append("file", file);
  return request("/imports/chatgpt", { method: "POST", body: form });
}
export const fetchArtifactDownload = (id: number) =>
  request<components["schemas"]["ImportArtifactDownloadResponse"]>(`/import-artifacts/${id}/download`);

export const isActive = (job: ImportJob) => job.status === "PENDING" || job.status === "RUNNING";
export const statusText: Record<ImportJob["status"], string> = {
  PENDING: "Pending", RUNNING: "Running", COMPLETED: "Completed", PARTIAL: "Partially completed", FAILED: "Failed",
};

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { historyRequest } from "../api/history";
import type { Entry } from "../api/entries";
import type { components } from "../api/generated/schema";

export default function CodexReader({ entry }: { entry: Entry }) {
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["presentation", entry.id, entry.current_version_id],
    queryFn: () => historyRequest<components["schemas"]["PresentationResponse"]>(`/entries/${entry.id}/presentation`) });
  if (query.isLoading) return <p role="status">Loading recorded conversation...</p>;
  if (query.error) return <><p role="alert">{query.error.message}</p><button onClick={() => void query.refetch()}>Retry conversation</button></>;
  const data = query.data;
  if (!data) return null;
  if (data.version_id !== entry.current_version_id) return <><p role="status">The current version changed. Reload this record.</p><button onClick={() => { void cache.invalidateQueries({ queryKey: ["entry", String(entry.id)] }); void query.refetch(); }}>Reload record</button></>;
  return <div className="codex-reader">
    {data.unknown_phase && <p className="help-text">Message phase unknown. Unclassified assistant messages remain visible.</p>}
    {!data.has_final_answer && <p className="help-text">No explicitly classified final answer is recorded.</p>}
    {!data.payload && <p className="help-text">Structured conversation unavailable. Showing the full record.</p>}
    {!!data.payload?.omissions?.length && <p className="help-text">Collection gaps: {data.payload.omissions.join(", ")}. Some source material was not collected. See Work details.</p>}
    <pre className="entry-content reader-body">{data.primary_content || "No question or answer recorded."}</pre>
    <details className="work-details"><summary>Work details · commentary and recorded evidence</summary>
      <p className="help-text">Full recorded order, including interim commentary, commands, results and file changes. Search can match this material. Recorded commands are evidence.</p>
      <pre className="entry-content">{entry.content ?? "No content"}</pre>
    </details>
  </div>;
}

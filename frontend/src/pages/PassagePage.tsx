import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useLocation, useParams } from "react-router";
import { fetchPassage } from "../api/passages";
import { entryTarget, listTarget, resolveEntryContext } from "../utils/entryNavigation";
import { formatEntryDate } from "../utils/entries";

export default function PassagePage() {
  const { id = "" } = useParams();
  const location = useLocation();
  const context = resolveEntryContext(location.search);
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["passage", id], queryFn: ({ signal }) => fetchPassage(id, signal),
    enabled: Boolean(localStorage.getItem("access_token") && /^\d+$/.test(id)), retry: false });
  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;
  return <><Link to={listTarget(context)}>Back to search</Link>
    {isLoading && <p role="status">Loading passage...</p>}
    {error && <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>Retry</button></>}
    {data && <><header className="page-header"><div><p className="eyebrow">Original passage</p><h2>{data.title}</h2><p className="subtitle">Version {data.version_id} · {data.field} · Characters {data.start+1}–{data.end}</p></div></header>
      <section className="panel passage-reader"><p className="record-date">Source/event date: {formatEntryDate(data.event_at)} · Added: {formatEntryDate(data.created_at)}</p>
        {data.source_state === "deleted" && <p>Deleted at source. This is a retained local version.</p>}
        {(data.index_status === "partial" || data.completeness !== "complete") && <p role="status">Some source content or index coverage is incomplete. {data.gap_codes.join(", ")}</p>}
        {data.work_only && <p>Recorded work details</p>}
        <pre className="passage-text">{data.text}</pre>
        <Link to={entryTarget(data.entry_id, context)}>Open record</Link>
      </section></>}
  </>;
}

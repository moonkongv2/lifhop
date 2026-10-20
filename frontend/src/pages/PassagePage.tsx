import type { components } from "../api/generated/schema";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useLocation, useParams } from "react-router";
import { fetchCitation, fetchPassage, type Passage } from "../api/passages";
import { fetchSemanticSlice } from "../api/semantic";
import { entryTarget, listTarget, resolveEntryContext } from "../utils/entryNavigation";
import { formatEntryDate } from "../utils/entries";

export default function PassagePage({ semantic = false }: { semantic?: boolean }) {
  const { id = "" } = useParams();
  const location = useLocation();
  const context = resolveEntryContext(location.search);
  const anchor = new URLSearchParams(location.search);
  const conversationReturn = /^\/conversations\/[a-f0-9]{32}$/.test(anchor.get("returnTo") ?? "") ? anchor.get("returnTo") : null;
  const pinned = ["version_id", "field", "start", "end", "passage_hash"].some(key => anchor.has(key));
  const token = localStorage.getItem("access_token");
  const { data, error, isLoading, isFetching, refetch } = useQuery<Passage | components["schemas"]["CitationResponse"]>({ queryKey: [semantic ? "semantic-slice" : "passage", id, location.search, token], queryFn: ({ signal }) => pinned ? fetchCitation(anchor, signal) : semantic ? fetchSemanticSlice(id, signal) : fetchPassage(id, signal),
    enabled: Boolean(localStorage.getItem("access_token") && (pinned || /^\d+$/.test(id))), retry: false, gcTime: 0, refetchOnMount: "always" as const });
  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;
  return <><Link to={conversationReturn ?? listTarget(context)}>{conversationReturn ? "Back to conversation" : "Back to search"}</Link>
    {isLoading && <p role="status">Loading passage...</p>}
    {error && <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>Retry</button></>}
    {data && !isFetching && !error && <><header className="page-header"><div><p className="eyebrow">Original passage</p><h2>{data.title}</h2><p className="subtitle">Version {data.version_id} · {data.field} · Characters {data.start+1}–{data.end}</p></div></header>
      <section className="panel passage-reader"><p className="record-date">Source/event date: {formatEntryDate(data.event_at)} · Added: {formatEntryDate(data.created_at)}</p>
        {data.source_state === "deleted" && <p>Deleted at source. This is a retained local version.</p>}
        {data.source_state === "unavailable" && <p>External source is unavailable. Showing a retained local version.</p>}
        {"freshness" in data && <><p role="status">{data.freshness === "updated" ? `This record has changed. Showing the cited version ${data.version_id}; current version: ${data.current_version_id ?? "unavailable"}.` : "This citation matches the current retained version."}</p><p className="help-text">Version observed: {formatEntryDate(data.observed_at)}. This is retained evidence, not a reconstruction of past state.</p></>}
        {"freshness" in data && data.completeness !== "complete" && <p role="status">The cited source version is incomplete.</p>}
        {!("freshness" in data) && (data.index_status === "partial" || data.completeness !== "complete") && <p role="status">Some source content or index coverage is incomplete. {data.gap_codes.join(", ")}</p>}
        {!("freshness" in data) && data.work_only && <p>Recorded work details</p>}
        <pre className="passage-text">{data.text}</pre>
        <Link to={entryTarget(data.entry_id, context)}>Open current record</Link>
      </section></>}
  </>;
}

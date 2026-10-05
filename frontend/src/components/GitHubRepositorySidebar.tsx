import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { historyRequest } from "../api/history";
import { githubEntryTarget, repositoryRecordsUrl, repositoryTarget } from "../utils/githubRepositories";
import type { RepositoryContext, RepositoryRecords } from "../utils/githubRepositories";

export default function GitHubRepositorySidebar({selectedId,context}: {selectedId:number; context:RepositoryContext}) {
  const url = repositoryRecordsUrl(context);
  const records = useQuery({queryKey:["github-records",url],queryFn:()=>historyRequest<RepositoryRecords>(url)});
  return <aside className="panel reader-sidebar" aria-label="Record navigation"><h3>Repository records</h3>
    <p className="help-text">{context.tab === "documents" ? context.path : "Your current repository page"}</p>
    {records.isLoading && <p>Loading records...</p>}
    {records.error && <><p>Record navigation is unavailable.</p><button onClick={()=>void records.refetch()}>Retry records</button></>}
    {records.data?.items.length === 0 && <p>No records in this view.</p>}
    {records.data?.items.map(record=><Link key={record.id} className="sidebar-record" to={githubEntryTarget(record.id,context)} aria-current={record.id===selectedId ? "page" : undefined}>
      <span>{record.title}</span><small>{record.sha?.slice(0,8)} · {record.id===selectedId ? "Reading now" : "Open record"}</small></Link>)}
    <Link className="button-link" to={repositoryTarget(context)}>Back to repository</Link>
  </aside>;
}

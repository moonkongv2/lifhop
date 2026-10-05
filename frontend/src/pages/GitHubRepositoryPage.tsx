import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { historyRequest } from "../api/history";
import { listTarget } from "../utils/entryNavigation";
import { repositoryContext, repositoryTarget, repositoryRecordsUrl, githubEntryTarget, eventDay } from "../utils/githubRepositories";
import type { RepositorySummary, RepositoryRecords, RepositoryDocuments, RepositoryContext } from "../utils/githubRepositories";
import { formatEntryDate } from "../utils/entries";
import GitHubRecordStatus from "../components/GitHubRecordStatus";

export default function GitHubRepositoryPage() {
  const [params, setParams] = useSearchParams();
  const context = repositoryContext(params);
  const scope = context?.scope;
  const summary = useQuery({queryKey:["github-repository",scope], enabled:!!context,
    queryFn:()=>historyRequest<RepositorySummary>(`/github-repositories?${new URLSearchParams({scope:scope!})}`)});
  const documents = context?.tab === "documents" && !context.path;
  const url = context ? documents
    ? `/github-repositories/documents?${new URLSearchParams({scope:context.scope,limit:"20",offset:String(context.doc_offset)})}`
    : repositoryRecordsUrl(context) : "";
  const rows = useQuery({queryKey:["github-records",url], enabled:!!context && !!summary.data,
    queryFn:()=>historyRequest<RepositoryRecords | RepositoryDocuments>(url)});
  const pageKey = documents ? "doc_offset" : context?.tab === "documents" ? "snapshot_offset" : "offset";
  const offset = context?.[pageKey] ?? 0;
  const data = rows.data;
  const serialized = params.toString();
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total) {
      const current = repositoryContext(new URLSearchParams(serialized));
      if (current) {
        current[pageKey] = Math.max(0, Math.ceil(data.total / 20)-1)*20;
        setParams(new URLSearchParams(repositoryTarget(current).split("?")[1]), {replace:true});
      }
    }
  },[data,offset,pageKey,serialized,setParams]);
  function change(next: RepositoryContext) { setParams(new URLSearchParams(repositoryTarget(next).split("?")[1])); }
  if (!context) return <section className="panel"><h2>GitHub repository</h2><p role="alert">Invalid repository view. Check the scope, document path, and page values.</p><Link to="/entries">Back to entries</Link></section>;
  const repo = summary.data;
  return <>
    <Link className="back-link" to={listTarget(context.outer)}>← {context.outer.pathname === "/search" ? "Back to search" : "Back to entries"}</Link>
    <section className="panel repository-header">
      <span className="badge source">GitHub repository</span><h2>{repo?.repository ?? context.scope}</h2>
      {summary.isLoading && <p role="status">Loading repository...</p>}
      {summary.error && <><p role="alert">{summary.error.message}</p><button onClick={()=>void summary.refetch()}>Retry repository</button></>}
      {repo && <>
        <p>{repo.commit_count} retained commits · {repo.document_count} document paths · {repo.snapshot_count} snapshots{repo.unclassified_count ? ` · ${repo.unclassified_count} unclassified records` : ""}</p>
        <p className="record-date">Source period: {formatEntryDate(repo.start_at)} – {formatEntryDate(repo.end_at)} (Asia/Seoul)</p>
        {!!repo.unknown_date_count && <p>{repo.unknown_date_count} records have an unknown source date.</p>}
        {(repo.partial || repo.review_required) && <p className="help-text">Some retained evidence is partial or needs version review.</p>}
        <p className="help-text">Counts describe retained records. <Link to="/sources">View collection coverage in Sources</Link>.</p>
      </>}
    </section>
    {repo && <section className="panel repository-browser" aria-label="Repository records">
      <nav className="repository-tabs" aria-label="Repository views">{(["commits","documents",...(repo.unclassified_count || context.tab === "unclassified" ? ["unclassified"] : [])] as RepositoryContext["tab"][]).map(tab =>
        <button key={tab} aria-current={context.tab === tab ? "page" : undefined} onClick={()=>change({...context,tab})}>{tab === "commits" ? "Commits" : tab === "documents" ? "Documents" : "Unclassified"}</button>)}</nav>
      {context.tab === "documents" && <p className="help-text">Latest retained snapshots describe stored history. They may differ from the current GitHub files or a selected branch head.</p>}
      {context.tab === "documents" && context.path && <><button onClick={()=>change({...context,path:null,snapshot_offset:0})}>All documents</button><h3 className="repository-path">{context.path}</h3></>}
      {rows.isLoading && <p role="status">Loading records...</p>}
      {rows.error && <><p role="alert">{rows.error.message}</p><button onClick={()=>void rows.refetch()}>Retry records</button></>}
      {data && <>
        <div className="records-toolbar"><p>{data.total} {documents ? "document paths" : "records"} · Page {Math.floor(offset/20)+1}</p><span>{documents ? "Path order" : "Source date · Newest first"}</span></div>
        {!data.items.length && <p>No retained {documents ? "documents" : "records"} in this view.</p>}
        <div className="repository-rows">{data.items.map((row,index)=> {
          if ("latest" in row) {
            const selected = {...context,path:row.path,snapshot_offset:0};
            return <article className="repository-row" key={row.path}>
              <Link className="repository-path" to={repositoryTarget(selected)}>{row.path}</Link>
              <p className="record-date">{row.snapshot_count} snapshots · Latest retained snapshot: {formatEntryDate(row.latest.event_at)}</p>
              <GitHubRecordStatus record={row.latest} />
              <Link to={githubEntryTarget(row.latest.id,selected)}>Read latest retained snapshot</Link>
            </article>;
          }
          const previous = data.items[index-1];
          const newDay = index===0 || (previous && "event_at" in previous && eventDay(previous.event_at)!==eventDay(row.event_at));
          return <div key={row.id}>{newDay && <h3 className="repository-day">{eventDay(row.event_at)}</h3>}
            <article className="repository-row"><Link to={githubEntryTarget(row.id,context)}>{row.title}</Link>
              <p className="record-date"><code>{row.sha?.slice(0,8) ?? "SHA unavailable"}</code> · {formatEntryDate(row.event_at)}</p>
              <GitHubRecordStatus record={row} />
            </article></div>;
        })}</div>
        <div className="actions pagination"><button disabled={rows.isFetching || !offset} onClick={()=>change({...context,[pageKey]:Math.max(0,offset-20)})}>Previous page</button>
          <button disabled={rows.isFetching || offset+20>=data.total} onClick={()=>change({...context,[pageKey]:offset+20})}>Next page</button></div>
      </>}
    </section>}
  </>;
}

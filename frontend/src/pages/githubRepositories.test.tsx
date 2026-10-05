import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation, Link } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GitHubRepositoryPage from "./GitHubRepositoryPage";
import GitHubRepositorySidebar from "../components/GitHubRepositorySidebar";
import ArchiveResults from "../components/ArchiveResults";
import EntryResults from "../components/EntryResults";
import { repositoryContext, repositoryTarget, safeRepositoryContext } from "../utils/githubRepositories";
import { invalidateRecordViews } from "../utils/recordCache";

const summary = {source_scope:"repo:123",repository:"example/project",commit_count:25,document_count:25,
  snapshot_count:50,unclassified_count:1,unknown_date_count:1,start_at:null,end_at:null,partial:true,review_required:false};
const record = {id:7,title:"Historical change",sha:"a".repeat(40),event_at:"2026-01-01T00:00:00Z",
  current_version_id:8,source_state:"available",partial:false,review_required:false};
let requests: string[], empty:boolean, failed:boolean;
beforeEach(()=> {
  localStorage.setItem("access_token","test"); requests=[]; empty=false; failed=false;
  vi.stubGlobal("fetch", vi.fn(async(input:RequestInfo|URL)=>{
    const path=String(input); requests.push(path); const url=new URL(path,"http://test");
    if(path.includes("/api/archive")) return Response.json({items:[{kind:"github_repository",repository:summary}],total:1,limit:20,offset:0});
    if(path.includes("/api/entries/search")) return Response.json({items:[{...record,source:"github",provider:"github",type:"PROJECT_EVENT",content:"evidence",created_at:record.event_at,updated_at:record.event_at,
      repository_ref:{source_scope:"repo:123",repository:"example/project",kind:"commit"}}],total:1,limit:20,offset:0});
    if(url.pathname==="/api/github-repositories") return Response.json(summary);
    if(failed) return Response.json({detail:"Temporary query failure"},{status:503});
    if(url.pathname.endsWith("/documents")) return Response.json({items:empty?[]:[{path:"docs/history.md",snapshot_count:25,latest:record}],total:empty?0:25,limit:20,offset:Number(url.searchParams.get("offset"))});
    return Response.json({items:empty?[]:[record,{...record,id:9,title:"Earlier change",event_at:null}],total:empty?0:25,limit:20,offset:Number(url.searchParams.get("offset"))});
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();});
function Position(){const location=useLocation();return <output data-testid="position">{location.pathname+location.search}</output>;}
function Reader(){const location=useLocation();const context=safeRepositoryContext(new URLSearchParams(location.search).get("repositoryReturn"))!;
  return <><GitHubRepositorySidebar selectedId={7} context={context}/><Link to={repositoryTarget(context)}>Return to browser</Link></>;}
function mount(url:string,node:React.ReactNode=<GitHubRepositoryPage/>){
  const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[url]}><Position/><Routes>
    <Route path="/repositories/github" element={node}/><Route path="/entries/:id" element={<Reader/>}/>
    <Route path="/entries" element={node}/><Route path="/search" element={node}/>
  </Routes></MemoryRouter></QueryClientProvider>);return cache;
}
it("renders one repository card with retained counts and a browse link",async()=>{
  mount("/entries",<ArchiveResults/>);
  const link=await screen.findByRole("link",{name:"example/project"});
  expect(link.getAttribute("href")).toContain("scope=repo%3A123");
  expect(screen.getByText("25 retained commits · 25 document paths · 50 snapshots")).toBeTruthy();
  expect(screen.queryByText("Historical change")).toBeNull();
});
it("displays commit dates and unknown dates without full evidence",async()=>{
  mount("/repositories/github?scope=repo:123");
  await screen.findByRole("link",{name:"Historical change"});
  expect(screen.getByText("January 1, 2026")).toBeTruthy();expect(screen.getByText("Date unknown")).toBeTruthy();
  expect(screen.getByRole("button",{name:"Commits"}).getAttribute("aria-current")).toBe("page");
});
it("keeps document and snapshot pages across reading, sidebar navigation and returning",async()=>{
  mount("/repositories/github?scope=repo:123&tab=documents&doc_offset=20&returnTo=%2Fsearch%3Fq%3Dhistory");
  fireEvent.click(await screen.findByRole("link",{name:"docs/history.md"}));
  await screen.findByRole("link",{name:"Historical change"});
  fireEvent.click(screen.getByRole("button",{name:"Next page"}));
  await waitFor(()=>expect(screen.getByTestId("position").textContent).toContain("snapshot_offset=20"));
  fireEvent.click(await screen.findByRole("link",{name:"Historical change"}));
  await screen.findByRole("heading",{name:"Repository records"});
  fireEvent.click(screen.getByRole("link",{name:/Earlier change/}));
  const encoded=new URLSearchParams(screen.getByTestId("position").textContent!.split("?")[1]).get("repositoryReturn")!;
  expect(encoded).toContain("doc_offset=20");expect(encoded).toContain("snapshot_offset=20");
  fireEvent.click(screen.getByRole("link",{name:"Return to browser"}));
  await screen.findByRole("button",{name:"All documents"});
  fireEvent.click(screen.getByRole("button",{name:"All documents"}));
  await screen.findByRole("link",{name:"docs/history.md"});
  expect(screen.getByTestId("position").textContent).toContain("doc_offset=20");
  expect(screen.getByTestId("position").textContent).not.toContain("snapshot_offset");
});
it("loads deep-linked snapshot pages with independent offsets",async()=>{
  mount("/repositories/github?scope=repo:123&tab=documents&doc_offset=20&snapshot_offset=20&path=docs%2Fhistory.md");
  await screen.findByRole("link",{name:"Historical change"});
  expect(requests.some(p=>p.includes("document-snapshots")&&p.includes("offset=20")&&p.includes("path=docs%2Fhistory.md"))).toBe(true);
});
it("corrects an empty out-of-range page without losing the document path",async()=>{
  empty=true;
  mount("/repositories/github?scope=repo:123&tab=documents&doc_offset=20&snapshot_offset=40&path=docs%2Fhistory.md");
  await screen.findByText("No retained records in this view.");
  await waitFor(()=>expect(screen.getByTestId("position").textContent).not.toContain("snapshot_offset=40"));
  expect(screen.getByTestId("position").textContent).toContain("path=docs%2Fhistory.md");
});
it("shows retry and recovers a failed records request",async()=>{
  failed=true;mount("/repositories/github?scope=repo:123");
  await screen.findByRole("button",{name:"Retry records"});failed=false;
  fireEvent.click(screen.getByRole("button",{name:"Retry records"}));
  await screen.findByRole("link",{name:"Historical change"});
});
it("rejects invalid views without making a private API request",()=>{
  mount("/repositories/github?scope=repo:123&doc_offset=-1");
  expect(screen.getByRole("alert").textContent).toContain("Invalid repository view");expect(requests).toHaveLength(0);
});
it("adds a repository link to individual search results",async()=>{
  mount("/search?q=history",<EntryResults searching/>);
  expect((await screen.findByRole("link",{name:"Browse repository"})).getAttribute("href")).toContain("returnTo=%2Fsearch%3Fq%3Dhistory");
  expect(screen.getByRole("link",{name:"Historical change"}).getAttribute("href")).toContain("/entries/7?");
});
it("invalidates repository browsing alongside existing record views",async()=>{
  const cache=new QueryClient();cache.setQueryData(["github-repository","repo:123"],summary);
  cache.setQueryData(["github-records","records"],{items:[record]});
  await invalidateRecordViews(cache);
  expect(cache.getQueryState(["github-repository","repo:123"])?.isInvalidated).toBe(true);
  expect(cache.getQueryState(["github-records","records"])?.isInvalidated).toBe(true);
});
it("validates repository return paths and strips recursive or external destinations",()=>{
  for(const target of ["https://evil.test/repositories/github?scope=repo:123","//evil.test/x","/repositories/github?scope=repo:0",
    "/repositories/github?scope=repo:123&path=../secret","/repositories/github?scope=repo:123&snapshot_offset=9007199254740992"])
    expect(safeRepositoryContext(target)).toBeNull();
  const context=repositoryContext(new URLSearchParams("scope=repo:123&returnTo=https%3A%2F%2Fevil.test&repositoryReturn=recursive"))!;
  expect(repositoryTarget(context)).toContain("returnTo=%2Fentries");expect(repositoryTarget(context)).not.toContain("recursive");
});

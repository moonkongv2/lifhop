import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GitHubRepositoryPage from "./GitHubRepositoryPage";
import EntryResults from "../components/EntryResults";
import CollectionRuns from "../components/CollectionRuns";
import { repositoryContext, safeRepositoryContext, repositoryTarget } from "../utils/githubRepositories";

const root = {parent_kind:"pull_request",parent_id:"100",number:"1",title:"[Synthetic] Migration decision",root_entry_id:1,
  state:"merged",event_at:"2026-01-01T00:00:00Z",orphan:false,child_count:25,partial:false,review_required:false};
const row = {id:24,title:"[Synthetic] Code review comment",kind:"review_comment",sha:null,event_at:null,
  current_version_id:24,source_state:"available",partial:false,review_required:false};
let orphan:boolean, failed:boolean, requests:string[];
beforeEach(()=>{
  orphan=false;failed=false;requests=[];localStorage.setItem("access_token","test");
  vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
    const url=new URL(String(input),"http://test");requests.push(url.pathname+url.search);
    const parent=orphan ? {...root,root_entry_id:null,orphan:true,title:"PR #1 — Parent not retained",state:"unknown"} : root;
    if(url.pathname==="/api/github-repositories") return Response.json({source_scope:"repo:123",repository:"example/repo",commit_count:0,document_count:0,snapshot_count:0,
      unclassified_count:0,unknown_date_count:0,start_at:null,end_at:null,partial:false,review_required:false,pull_request_count:1,issue_count:0,comment_count:24,review_count:1,orphan_count:orphan?1:0});
    if(url.pathname==="/api/github-repositories/discussions") return failed ? Response.json({detail:"Temporary discussion failure"},{status:503}) : Response.json({items:[parent],total:1,limit:20,offset:Number(url.searchParams.get("offset")??0)});
    if(url.pathname.includes("/discussions/pull_request/100")) return Response.json({discussion:parent,items:[row],total:25,limit:20,offset:url.searchParams.has("focus_entry_id")?20:Number(url.searchParams.get("offset")??0)});
    if(url.pathname.endsWith("/github-presentation")) {
      const id=url.pathname.includes("/24/")?24:1;
      return Response.json({entry_id:id,version_id:id,locator:"https://github.com/example/repo/pull/1",related:[],related_has_more:false,commit_links:[],
        payload:{kind:id===1?"github_pull_request":"github_review_comment",repository:"example/repo",repository_id:123,object_id:id===1?100:400,number:1,
          author:"synthetic",body:id===1?"Preserved parent decision":"Preserved review answer",body_state:"available",omissions:[],filter_version:"test",
          ...(id===1?{state:"closed",merged:true,draft:false,commits:[],commits_complete:true}:{parent_kind:"pull_request",parent_id:100,path:"app/main.py",line:2,side:"RIGHT",diff_hunk:"-old\n+new"})}});
    }
    if(url.pathname.startsWith("/api/entries/search")) return Response.json({items:[{...row,provider:"github",source:"github",type:"PROJECT_EVENT",created_at:null,updated_at:null,
      repository_ref:{source_scope:"repo:123",repository:"example/repo",kind:"discussion",parent_kind:"pull_request",parent_id:"100"}}],total:1,limit:20,offset:0});
    if(url.pathname.startsWith("/api/entries/")) return Response.json({id:url.pathname.endsWith("/24")?24:1,current_version_id:url.pathname.endsWith("/24")?24:1,provider:"github",title:"Synthetic",content:"Preserved text"});
    if(url.pathname.startsWith("/api/collection-runs")) return Response.json([{id:1,provider:"github",scope:"repo:123",status:"empty",counts:{},expected_items:0,
      started_at:null,last_seen_at:null,completed_at:null,coverage:{repository:"example/repo",repository_id:123,commits:0,documents:0,branches:[],gaps:[],lower_bound:false,
        discussions:{records:{pull_request:0,issue:0,issue_comment:0,review:0,review_comment:0},walk_complete:true,started_at:null,finished_at:null,failed:0,excluded:0}}}]);
    throw new Error("Unexpected URL: "+url);
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();});
function Position(){const location=useLocation();return <output data-testid="position">{location.pathname+location.search}</output>;}
function mount(url:string,node:React.ReactNode=<GitHubRepositoryPage/>){
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[url]}>
    <Position/><Routes><Route path="/repositories/github" element={node}/><Route path="/search" element={node}/><Route path="/sources" element={node}/></Routes>
  </MemoryRouter></QueryClientProvider>);
}
it("groups discussions and opens a parent with lazy child reading",async()=>{
  mount("/repositories/github?scope=repo:123&tab=discussions");
  fireEvent.click(await screen.findByRole("link",{name:"[Synthetic] Migration decision"}));
  await screen.findByText("Preserved parent decision");
  expect(screen.queryByText("Preserved review answer")).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Read record"}));
  await screen.findByText("Preserved review answer");
  expect(screen.getByText("Recorded code context")).toBeTruthy();
});
it("focuses search on the correct child page and retains its return URL",async()=>{
  mount("/repositories/github?scope=repo:123&tab=discussions&thread_kind=pull_request&thread_id=100&focus_entry_id=24&returnTo=%2Fsearch%3Fq%3Dreview");
  await screen.findByText("Preserved review answer");
  await waitFor(()=>expect(screen.getByTestId("position").textContent).toContain("thread_offset=20"));
  expect(screen.getByRole("link",{name:/Back to search/}).getAttribute("href")).toBe("/search?q=review");
  const record=(await screen.findByRole("link",{name:"Open record and history"})).getAttribute("href")!;
  expect(new URLSearchParams(record.split("?")[1]).get("repositoryReturn")).toContain("thread_offset=20");
});
it("reads retained children when the parent is absent",async()=>{
  orphan=true;mount("/repositories/github?scope=repo:123&tab=discussions&thread_kind=pull_request&thread_id=100");
  await screen.findByText("Parent not retained. The remaining records are independently preserved.");
  expect(requests.some(path=>path==="/api/entries/1")).toBe(false);
  fireEvent.click(screen.getByRole("button",{name:"Read record"}));await screen.findByText("Preserved review answer");
});
it("validates filters and serializes kind, state and unknown dates",async()=>{
  mount("/repositories/github?scope=repo:123&tab=discussions");await screen.findByLabelText("Kind");
  fireEvent.change(screen.getByLabelText("Kind"),{target:{value:"issue"}});
  fireEvent.change(screen.getByLabelText("State"),{target:{value:"unknown"}});
  fireEvent.click(screen.getByLabelText("Unknown date"));fireEvent.click(screen.getByRole("button",{name:"Apply filters"}));
  await waitFor(()=>expect(requests.some(path=>path.includes("kind=issue")&&path.includes("state=unknown")&&path.includes("unknown_date=true"))).toBe(true));
});
it("recovers a failed list and gives each search hit a thread focus link",async()=>{
  failed=true;mount("/repositories/github?scope=repo:123&tab=discussions");
  const retry=await screen.findByRole("button",{name:"Retry discussions"});
  failed=false;fireEvent.click(retry);
  await screen.findByRole("link",{name:"[Synthetic] Migration decision"});cleanup();
  mount("/search?q=review",<EntryResults searching/>);
  const target=(await screen.findByRole("link",{name:"[Synthetic] Code review comment"})).getAttribute("href")!;
  expect(target).toContain("thread_id=100");expect(target).toContain("focus_entry_id=24");
});
it("shows successful empty discussion coverage in Sources",async()=>{
  mount("/sources",<CollectionRuns/>);fireEvent.change(screen.getByLabelText("Backfill source"),{target:{value:"github"}});
  await screen.findByText(/No discussions found in selected scope/);
  expect(screen.getByText(/Snapshot collected over a time window/)).toBeTruthy();
});
it("rejects invalid parent, focus and date contexts",()=>{
  for(const search of ["thread_kind=issue","thread_kind=review&thread_id=1","thread_kind=issue&thread_id=1&focus_entry_id=-1",
    "discussion_from=2026-02-30","unknown_date=true&discussion_from=2026-01-01"])
    expect(repositoryContext(new URLSearchParams("scope=repo:123&tab=discussions&"+search))).toBeNull();
  const safe=safeRepositoryContext("/repositories/github?scope=repo:123&tab=discussions&thread_kind=issue&thread_id=2&returnTo=https://evil.test")!;
  expect(repositoryTarget(safe)).toContain("returnTo=%2Fentries");
});

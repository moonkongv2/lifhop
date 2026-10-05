import { afterEach, beforeEach, it, expect, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CollectionRuns from "./CollectionRuns";
import GitHubReader from "./GitHubReader";
import type { Entry } from "../api/entries";

const entry: Entry = { id: 7, title: "GitHub commit", content: "Recorded content", current_version_id: 8,
  source: "github", provider: "github", source_scope: "repo:123", read_only: true, source_state: "available",
  external_ai_allowed: false, review_required: false, type: "PROJECT_EVENT", event_at: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
let presentation: Record<string, unknown>;
let paths: string[];
beforeEach(() => {
  localStorage.setItem("access_token", "test"); paths = [];
  presentation = { version_id: 8, locator: "https://github.com/example/repo/commit/abc", related: [{id:9, title:"README snapshot"}], related_has_more: false,
    payload: {kind:"github_commit", repository:"example/repo", sha:"abc", message:"Improve collector <script>alert(1)</script>", author:{name:"Author"}, committer:{name:"Committer"}, parents:[], omissions:["PATCH_UNAVAILABLE"], files:[{path:"src/main.py",status:"modified",additions:1,deletions:0,patch_state:"available",patch:"+<script>alert(2)</script>"}]}};
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input); paths.push(path);
    if (path.includes("github-presentation")) return Response.json(presentation);
    if (path.includes("provider=github")) return Response.json([{id:1,provider:"github",scope:"repo:123",status:"partial",started_at:null,last_seen_at:null,completed_at:null,expected_items:2,counts:{new:2}, coverage:{repository:"example/repo", repository_id:123,commits:1,documents:1,lower_bound:true,gaps:["PATCH_UNAVAILABLE"],branches:[{name:"main",head_sha:"abc",commits:1,walk_complete:true}]}}]);
    return Response.json([]);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });
function mount(node: React.ReactNode) {
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={["/entries/7?returnTo=%2Fsearch%3Fsource%3Dgithub"]}>{node}</MemoryRouter></QueryClientProvider>);
}
it("switches Sources provider and labels GitHub counts without session counts", async () => {
  mount(<CollectionRuns />);
  await screen.findByText("No backfill runs on this page.");
  fireEvent.change(screen.getByLabelText("Backfill source"), {target:{value:"github"}});
  await screen.findByText("Repository: example/repo (ID 123)");
  expect(screen.getByText(/Prepared: 1 commits · 1 document snapshots/)).toBeTruthy();
  expect(screen.queryByText(/Sessions:/)).toBeNull();
  expect(paths.some(p=>p.includes("provider=github&limit=20&offset=0"))).toBe(true);
});
it("shows structured evidence as inert text and preserves Search return links", async () => {
  mount(<GitHubReader entry={entry} />);
  await screen.findByText("Commit message");
  expect(document.querySelector("script")).toBeNull();
  const details = screen.getByText(/modified · src\/main.py/).closest("details")!;
  expect(details.open).toBe(false);
  fireEvent.click(details.querySelector("summary")!);
  expect(details.textContent).toContain("+<script>alert(2)</script>");
  expect(screen.getByRole("link", {name:"README snapshot"}).getAttribute("href")).toContain("returnTo=%2Fsearch%3Fsource%3Dgithub");
});
it("labels baseline documents and hides unsafe locators", async () => {
  presentation = {...presentation, locator:"javascript:alert(1)", payload:{kind:"github_document",repository:"example/repo",sha:"abc",blob_sha:"def",path:"README.md",snapshot_reason:"head_baseline",content:"Historical text",omissions:[]}};
  mount(<GitHubReader entry={entry} />);
  await screen.findByText("Historical text");
  expect(screen.getByText(/last edit date is unknown/)).toBeTruthy();
  expect(screen.queryByRole("link", {name:"Open GitHub source"})).toBeNull();
});
it("requires refresh when evidence belongs to a different selected version", async () => {
  presentation.version_id = 10;
  mount(<GitHubReader entry={entry} />);
  await screen.findByRole("button", {name:"Reload record"});
  expect(screen.queryByText("Commit message")).toBeNull();
});

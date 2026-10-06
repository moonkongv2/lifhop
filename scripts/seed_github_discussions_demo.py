"""Prepare or apply disposable synthetic PR/issue discussions; no GitHub requests."""
import argparse
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit
from app.collectors.bundle import private_write
from app.collectors.client import apply_bundle
from app.collectors.github_discussions import DiscussionConfig, Preparation, make_item, validate_bundle
from app.collectors.github_reader import RepositoryReader
from app.schemas.collection_run import GitHubCollectorItem, GitHubRunCreate
from app.acquisition.common import ProbeError


def prepare_demo(directory, cfg):
    if directory.is_symlink() or any(parent.is_symlink() for parent in directory.parents):
        raise ProbeError("Symlink output directories are not allowed")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    prep = Preparation(directory, cfg, RepositoryReader(directory/"cache", cfg))
    date = "2026-01-01T00:00:00Z"
    def source(id, number=1, **values):
        return dict(id=id,number=number,created_at=date,updated_at=date,
            user={"login":"synthetic-author","id":9},**values)
    roots = [dict(kind="pull_request",id=100,number=1),dict(kind="issue",id=200,number=2)]
    pr = source(100,title="[Synthetic] Preserve the migration decision",body="[Synthetic] Decision: retain PostgreSQL versions and keep record deletion independent. This is demonstration text.",
        state="closed",merged=True,merged_at=date,draft=False,base={"sha":"b"*40},head={"sha":"a"*40},merge_commit_sha="a"*40)
    issue = source(200,2,title="[Synthetic] Make failure states visible",body="[Synthetic] Show failed API reads separately from an empty source.",state="open")
    items = [make_item(pr,"pull_request",cfg,commits=["a"*40]),make_item(issue,"issue",cfg)]
    for index in range(23):
        items.append(make_item(source(1000+index,body=f"[Synthetic] Comment {index+1}: retained discussion evidence. "+("Search marker: discussion-focus-demo" if index==22 else "")),"issue_comment",cfg,roots[0]))
    items.append(make_item(source(2000,2,body="[Synthetic] Issue comment: confirm the empty and failed states differ."),"issue_comment",cfg,roots[1]))
    items.append(make_item(source(300,body="",state="APPROVED",submitted_at=date,commit_id="a"*40),"review",cfg,roots[0]))
    items.append(make_item(source(301,body="[Synthetic] Draft review not submitted.",state="PENDING",submitted_at=None,commit_id="a"*40),"review",cfg,roots[0]))
    for id in (400,401):
        items.append(make_item(source(id,body="[Synthetic] Keep the owner check before reading related records.",
            path="app/example.py",line=12,side="RIGHT",original_line=10,commit_id="a"*40,original_commit_id="b"*40,
            pull_request_review_id=300,in_reply_to_id=400 if id==401 else None,
            diff_hunk="@@ -10 +12 @@\n-old synthetic example\n+new synthetic example"),"review_comment",cfg,roots[0]))
    for item in items:
        if not item.title.startswith("[Synthetic]"):
            item.title = "[Synthetic] " + item.title
        prep.store(item)
    prep.state.update(roots=roots,discovered={"pull_request":[100],"issue":[200]},processed=["pull_request:100","issue:200"],complete=True)
    for cursor in prep.state["lists"].values():
        cursor["done"] = True
    prep.save()
    return prep.seal()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email")
    parser.add_argument("--base-url",default="http://localhost:8000")
    parser.add_argument("--prepare-only",action="store_true")
    parser.add_argument("--run-dir",type=Path)
    args = parser.parse_args()
    if not args.prepare_only and not args.email:
        parser.error("--email is required unless --prepare-only is selected")
    if urlsplit(args.base_url).hostname not in {"localhost","127.0.0.1","::1"}:
        parser.error("Synthetic verification requires a local API")
    directory = args.run_dir or Path(".local/verification")/("github-discussions-demo-"+uuid4().hex)
    cfg = DiscussionConfig(repository="example/lifhop-discussions-synthetic",repository_id=int(uuid4().hex[:12],16))
    manifest = prepare_demo(directory,cfg)
    config_path = directory.with_name(directory.name+"-config.json")
    private_write(config_path,cfg.model_dump(mode="json"))
    print(f"Synthetic preview: {directory/'preview.html'} ({manifest['expected_items']} records)")
    print(f"Synthetic config: {config_path}")
    if args.prepare_only:
        return
    apply_bundle(directory,cfg,args.base_url,args.email,validator=validate_bundle,item_type=GitHubCollectorItem,run_type=GitHubRunCreate)
    print("No GitHub source was fetched or modified. Every invocation creates a disposable synthetic repository.")
    print(f"Open http://localhost:5173/repositories/github?scope=repo:{cfg.repository_id}&tab=discussions")
    print("Expected: one PR, one issue, paginated comments, empty approved review, draft review, code reply/context.")
    print("Search discussion-focus-demo to open the matching comment page. Inspect per-record history and deletion.")


if __name__ == "__main__":
    main()

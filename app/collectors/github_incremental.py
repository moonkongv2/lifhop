"""Bounded graph discovery and rotating mutable-thread reads for leased jobs."""
from copy import deepcopy
from datetime import datetime, timezone
import re
from urllib.parse import quote
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.acquisition.common import ProbeError
from app.collectors.bundle import bytes_json, digest, private_write, read_json
from app.collectors.github import Preparation as HistoryPreparation, FILTER
from app.collectors.github_discussions import make_item as discussion_item, source_id
from app.collectors.github_reader import Paused
from app.importers.github_discussions import DISCUSSION_OBJECTS
from app.models.collection_job import GitHubCommitCursor, GitHubThreadCursor
from app.schemas.collection_run import GitHubCollectorItem, GitHubRunCreate

PARSER = "github-incremental-rest-v1"
FORMAT = "lifhop-github-incremental-v1"
GRAPH_STEPS = 50
THREADS_PER_CYCLE = 3
PAGES_PER_THREAD = 3
RUN_FIELDS = ("client_run_uuid", "provider", "scope", "manifest_digest", "parser_version",
    "filter_version", "expected_items", "coverage")


class Preparation(HistoryPreparation):
    def __init__(self, directory, cfg, reader, bind, subscription):
        super().__init__(directory, cfg, reader)
        self.bind, self.sub_id, self.revision = bind, subscription.id, subscription.revision
        if "incremental" not in self.state:
            self.state["incremental"] = dict(progress=deepcopy(subscription.progress), nodes={}, threads={},
                selection=deepcopy(subscription.discussion_selection), graph_done=False,
                branch_counts={},
                selected_threads=None, threads_done=[], pages_read=0, roots_checked=0,
                started_at=datetime.now(timezone.utc).isoformat())
            self.save()
        self.work = self.state["incremental"]

    def get(self, suffix, *, refresh=False):
        path = f"/repos/{self.cfg.repository}" + suffix
        return self.reader.get(path, refresh=True) if refresh else self.reader.get(path)

    def store(self, item):
        item = item.model_copy(update={"parser_version": PARSER})
        previous = next((row for row in self.state["items"] if row["external_id"] == item.external_id), None)
        if previous and previous["payload_digest"] != digest(item.model_dump(mode="json")):
            self.gap("MUTABLE_SOURCE_CHANGED")
        super().store(item)

    def node(self, sha):
        if sha in self.work["nodes"]:
            return self.work["nodes"][sha]
        with Session(self.bind) as db:
            row = db.scalar(select(GitHubCommitCursor).where(GitHubCommitCursor.subscription_id == self.sub_id,
                GitHubCommitCursor.revision == self.revision, GitHubCommitCursor.sha == sha))
            return dict(parents=row.parents, ancestry_complete=row.ancestry_complete) if row else None

    def walk(self, branch, remaining):
        stack = branch["stack"]
        while stack and remaining:
            remaining -= 1
            sha, exiting = stack[-1]
            node = self.node(sha)
            if node and node["ancestry_complete"]:
                stack.pop()
            elif exiting:
                if node is None or any(not (self.node(parent) or {}).get("ancestry_complete") for parent in node["parents"]):
                    raise Paused("SOURCE_CONFLICT")
                self.work["nodes"][sha] = dict(parents=node["parents"], ancestry_complete=True)
                stack.pop()
            else:
                if node is None:
                    body, _ = self.get(f"/commits/{sha}?per_page=100&page=1")
                    parents = [parent["sha"] for parent in body["parents"]]
                    if body["sha"] != sha or any(not re.fullmatch(r"[a-f0-9]{40}", parent) for parent in parents):
                        raise Paused("SOURCE_CONFLICT")
                    self.commit(sha)  # Existing sanitization, paginated diffs and historical documents.
                    node = dict(parents=parents, ancestry_complete=False)
                    self.work["nodes"][sha] = node
                    self.state["processed"].append(sha)
                ancestors = {frame[0] for frame in stack if frame[1]}
                if any(parent in ancestors or parent == sha for parent in node["parents"]):
                    raise Paused("SOURCE_CONFLICT")
                stack[-1] = [sha, True]
                stack.extend([parent, False] for parent in reversed(node["parents"]))
                if len(stack) > 100000:
                    raise Paused("SOURCE_LIMIT")
            self.save()
        if not stack:
            branch["completed_head"] = branch["target_head"]
        return remaining

    def graph(self):
        remaining = GRAPH_STEPS
        branches = self.work["progress"].setdefault("branches", {})
        # Rotate branch priority so a deep first branch cannot starve another.
        names = list(dict.fromkeys(self.cfg.branches))
        start = self.work["progress"].get("branch_offset", 0) % len(names)
        for name in names[start:] + names[:start]:
            head, _ = self.get("/branches/" + quote(name, safe=""))
            sha = head["commit"]["sha"]
            if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
                raise Paused("FORMAT_UNSUPPORTED")
            branch = branches.setdefault(name, dict(stack=[], completed_head=None, documents_head=None))
            branch["observed_head"] = sha
            if not branch["stack"] and branch["completed_head"] != sha:
                branch["target_head"], branch["stack"] = sha, [[sha, False]]
            if branch["stack"]:
                before_count = len(self.state["processed"])
                remaining = self.walk(branch, remaining)
                self.work["branch_counts"][name] = len(self.state["processed"]) - before_count
            if branch["documents_head"] != sha:
                commit, _ = self.get(f"/commits/{sha}?per_page=100&page=1")
                if commit["sha"] != sha:
                    raise Paused("SOURCE_CONFLICT")
                mappings = []
                for path, _ in self.tree_documents(commit["commit"]["tree"]["sha"]):
                    existing = next((d for d in self.state["documents"] if d["sha"] == sha and d["path"] == path), None)
                    identity = existing["external_id"] if existing else self.document(commit, path, "head_baseline")
                    if identity:
                        mappings.append(dict(head_sha=sha, path=path, external_id=identity))
                branch["head_documents"], branch["documents_head"] = mappings, sha
            self.save()
        self.work["progress"]["branch_offset"] = (start + 1) % len(names)
        self.work["graph_done"] = True
        self.save()

    def root(self, number, kind):
        key = str(number)
        if key not in self.work["threads"]:
            with Session(self.bind) as db:
                row = db.scalar(select(GitHubThreadCursor).where(GitHubThreadCursor.subscription_id == self.sub_id,
                    GitHubThreadCursor.revision == self.revision, GitHubThreadCursor.number == key))
                self.work["threads"][key] = dict(number=key, kind=kind, progress=deepcopy(row.progress) if row else {},
                    last_checked_at=row.last_checked_at.isoformat() if row and row.last_checked_at else None)
        root = self.work["threads"][key]
        if root["kind"] != kind:
            raise Paused("SOURCE_CONFLICT")
        return root

    def list_roots(self, page, sort):
        path = f"/issues?state=all&sort={sort}&direction={'asc' if sort == 'created' else 'desc'}&per_page=100&page={page}"
        rows, headers = self.get(path)
        if not isinstance(rows, list):
            raise Paused("FORMAT_UNSUPPORTED")
        for row in rows:
            number = source_id(row["number"])
            if number not in self.work["selection"]["exclude_numbers"]:
                self.root(number, "pull_request" if "pull_request" in row else "issue")
        next_page = self.reader.next_page(headers, f"/repos/{self.cfg.repository}" + path)
        if next_page is not None and (next_page <= page or next_page > self.cfg.max_pages):
            raise Paused("PAGE_LIMIT")
        return next_page

    def select_threads(self):
        progress = self.work["progress"]
        page = progress.get("discussion_page", 1)
        next_page = self.list_roots(page, "created")
        self.list_roots(1, "updated")
        progress["discussion_page"] = next_page or 1
        if next_page is None:
            progress["inventory_completed_at"] = datetime.now(timezone.utc).isoformat()
        with Session(self.bind) as db:
            rows = db.scalars(select(GitHubThreadCursor).where(GitHubThreadCursor.subscription_id == self.sub_id,
                GitHubThreadCursor.revision == self.revision)
                .order_by(GitHubThreadCursor.last_checked_at.asc().nullsfirst(), GitHubThreadCursor.id)
                .limit(THREADS_PER_CYCLE))
            for row in rows:
                self.root(int(row.number), row.kind)
            # Reserve reconciliation capacity even while new roots keep arriving.
            oldest = db.scalar(select(GitHubThreadCursor).where(GitHubThreadCursor.subscription_id == self.sub_id,
                GitHubThreadCursor.revision == self.revision, GitHubThreadCursor.last_checked_at.is_not(None))
                .order_by(GitHubThreadCursor.last_checked_at, GitHubThreadCursor.id).limit(1))
            if oldest:
                self.root(int(oldest.number), oldest.kind)
        candidates = sorted(self.work["threads"].values(), key=lambda row: (row["last_checked_at"] or "", int(row["number"])))
        selected = [row["number"] for row in candidates[:THREADS_PER_CYCLE]]
        if oldest and oldest.number not in selected:
            selected[-1] = oldest.number
        self.work["selected_threads"] = selected
        self.save()

    def thread(self, root):
        number, kind = int(root["number"]), root["kind"]
        endpoint = f"/{'pulls' if kind == 'pull_request' else 'issues'}/{number}"
        before, _ = self.get(endpoint, refresh=True)
        root_id = source_id(before["id"])
        if source_id(before["number"]) != number:
            raise Paused("SOURCE_CONFLICT")
        progress = root["progress"]
        if not progress or progress["updated_at"] != before.get("updated_at"):
            progress = dict(updated_at=before.get("updated_at"), object_id=root_id, stream=0, page=1, commits=[])
            root["progress"] = progress
        if progress["object_id"] != root_id:
            raise Paused("SOURCE_CONFLICT")
        parent = dict(kind=kind, id=root_id, number=number)
        streams = [("issue_comment", f"/issues/{number}/comments")]
        if kind == "pull_request":
            streams += [("review", endpoint + "/reviews"), ("review_comment", endpoint + "/comments"),
                ("commits", endpoint + "/commits")]
        pages = 0
        while progress["stream"] < len(streams) and pages < PAGES_PER_THREAD:
            record_kind, suffix = streams[progress["stream"]]
            path = suffix + f"?per_page=100&page={progress['page']}"
            rows, headers = self.get(path, refresh=True)
            if not isinstance(rows, list):
                raise Paused("FORMAT_UNSUPPORTED")
            for row in rows:
                if record_kind == "commits":
                    sha = row["sha"]
                    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
                        raise Paused("FORMAT_UNSUPPORTED")
                    if sha not in progress["commits"]:
                        progress["commits"].append(sha)
                    if len(progress["commits"]) > 250:
                        raise Paused("SOURCE_LIMIT")
                else:
                    item = discussion_item(row, record_kind, self.cfg, parent)
                    self.store(item)
                    for gap in item.payload.omissions:
                        self.gap(gap)
            next_page = self.reader.next_page(headers, f"/repos/{self.cfg.repository}" + path)
            if next_page is not None and (next_page <= progress["page"] or next_page > self.cfg.max_pages):
                raise Paused("PAGE_LIMIT")
            if next_page is None:
                progress["stream"], progress["page"] = progress["stream"] + 1, 1
            else:
                progress["page"] = next_page
            pages += 1
            self.work["pages_read"] += 1
            self.save()
        after, _ = self.get(endpoint, refresh=True)
        if after.get("id") != root_id or after.get("number") != number or after.get("updated_at") != progress["updated_at"]:
            self.gap("MUTABLE_SOURCE_CHANGED")
            return
        if progress["stream"] == len(streams):
            complete = kind != "pull_request" or after.get("commits") == len(progress["commits"])
            item = discussion_item(after, kind, self.cfg, commits=progress["commits"], commits_complete=complete,
                extra_gaps=[] if complete else ["PR_COMMIT_MEMBERSHIP_INCOMPLETE"])
            self.store(item)
            for gap in item.payload.omissions:
                self.gap(gap)
            root["progress"], root["last_checked_at"] = {}, datetime.now(timezone.utc).isoformat()
            self.work["roots_checked"] += 1
        self.save()

    def run(self):
        repo, _ = self.get("")
        if repo.get("id") != self.cfg.repository_id:
            raise Paused("SOURCE_CONFLICT")
        if not self.work["graph_done"]:
            self.graph()
        if self.work["selection"]["enabled"]:
            if self.work["selected_threads"] is None:
                self.select_threads()
            for number in self.work["selected_threads"]:
                if number not in self.work["threads_done"]:
                    self.thread(self.work["threads"][number])
                    self.work["threads_done"].append(number)
                    self.save()
        self.state["complete"] = True
        self.save()

    def seal(self):
        branches = self.work["progress"].get("branches", {})
        counts = {kind: 0 for kind in DISCUSSION_OBJECTS}
        commits = documents = 0
        for row in self.state["items"]:
            kind = row["external_id"].split(":")[2]
            if kind == "commit":
                commits += 1
            elif kind == "document":
                documents += 1
            else:
                counts[kind] += 1
        enabled = self.work["selection"]["enabled"]
        coverage = dict(repository=self.cfg.repository, repository_id=self.cfg.repository_id,
            branches=[dict(name=name, head_sha=row["observed_head"],
                walk_complete=not self.state["gaps"] and row.get("completed_head") == row["observed_head"],
                commits=self.work["branch_counts"].get(name, 0)) for name, row in branches.items()],
            commits=commits, documents=documents, lower_bound=bool(self.state["gaps"]), gaps=sorted(self.state["gaps"]),
            head_documents=[item for row in branches.values() for item in row.get("head_documents", [])],
            incremental=dict(graph_pending=sum(len(row["stack"]) + int(row.get("target_head") != row["observed_head"]) for row in branches.values()),
                discussion_scan_page=self.work["progress"].get("discussion_page", 1),
                discussion_roots_checked=self.work["roots_checked"], discussion_pages_read=self.work["pages_read"], discussions_enabled=enabled))
        if enabled:
            coverage["discussions"] = dict(records=counts, discovered_pull_requests=sum(row["kind"] == "pull_request" for row in self.work["threads"].values()),
                discovered_issues=sum(row["kind"] == "issue" for row in self.work["threads"].values()), walk_complete=False,
                started_at=self.work["started_at"], finished_at=datetime.now(timezone.utc).isoformat(), failed=0, excluded=0)
        manifest = dict(bundle_format=FORMAT, client_run_uuid=self.state["client_run_uuid"], provider="github",
            scope=f"repo:{self.cfg.repository_id}", config_digest=digest(self.cfg.model_dump(mode="json")), parser_version=PARSER,
            filter_version=FILTER, expected_items=len(self.state["items"]), items=self.state["items"], coverage=coverage,
            checkpoint=dict(progress=self.work["progress"], nodes=self.work["nodes"], threads=self.work["threads"]))
        manifest["manifest_digest"] = digest(manifest)
        GitHubRunCreate.model_validate({key: manifest[key] for key in RUN_FIELDS})
        private_write(self.directory / "manifest.json", manifest)
        return manifest


def validate_bundle(directory, cfg):
    manifest = read_json(directory / "manifest.json", 32 * 1024 * 1024)
    check = dict(manifest)
    expected = check.pop("manifest_digest")
    if (digest(check) != expected or manifest["bundle_format"] != FORMAT or manifest["parser_version"] != PARSER or
            manifest["filter_version"] != FILTER or manifest["config_digest"] != digest(cfg.model_dump(mode="json")) or
            manifest["scope"] != f"repo:{cfg.repository_id}"):
        raise ProbeError("Incremental bundle identity/integrity mismatch")
    GitHubRunCreate.model_validate({key: manifest[key] for key in RUN_FIELDS})
    identities = set()
    for row in manifest["items"]:
        if row["external_id"] in identities:
            raise ProbeError("Invalid incremental payload path/identity")
        identities.add(row["external_id"])
        if row["file"] is None:
            if (row["error_code"] != "INVALID_ITEM" or
                    row["payload_digest"] != digest(dict(external_id=row["external_id"], error_code="INVALID_ITEM")) or
                    not re.fullmatch(r"repo:" + str(cfg.repository_id) + r":(?:commit:[a-f0-9]{40}|document:[a-f0-9]{40}:[a-f0-9]{64})", row["external_id"])):
                raise ProbeError("Invalid body-free outcome")
            continue
        if row["error_code"] is not None or not re.fullmatch(r"item-[a-f0-9]{64}\.json", row["file"]):
            raise ProbeError("Invalid incremental payload path")
        data = read_json(directory / row["file"], cfg.turn_bytes)
        item = GitHubCollectorItem.model_validate(data)
        if (item.external_id != row["external_id"] or item.source_scope != manifest["scope"] or
                item.payload.repository != cfg.repository or digest(data) != row["payload_digest"] or
                item.parser_version != PARSER or item.payload.filter_version != FILTER):
            raise ProbeError("Incremental body differs from frozen bundle")
    if len(identities) != manifest["expected_items"] or len(bytes_json(manifest["checkpoint"])) > 32 * 1024 * 1024:
        raise ProbeError("Invalid incremental checkpoint/count")
    return manifest


def advance(db, sub, manifest):
    """Caller checked the lease and every receipt; one transaction with job finish."""
    checkpoint = manifest["checkpoint"]
    for sha, value in checkpoint["nodes"].items():
        row = db.scalar(select(GitHubCommitCursor).where(GitHubCommitCursor.subscription_id == sub.id,
            GitHubCommitCursor.revision == sub.revision, GitHubCommitCursor.sha == sha))
        if row is None:
            row = GitHubCommitCursor(subscription_id=sub.id, revision=sub.revision, sha=sha)
            db.add(row)
        row.parents, row.ancestry_complete = value["parents"], value["ancestry_complete"]
    for number, value in checkpoint["threads"].items():
        row = db.scalar(select(GitHubThreadCursor).where(GitHubThreadCursor.subscription_id == sub.id,
            GitHubThreadCursor.revision == sub.revision, GitHubThreadCursor.number == number))
        if row is None:
            row = GitHubThreadCursor(subscription_id=sub.id, revision=sub.revision, number=number)
            db.add(row)
        row.kind, row.progress = value["kind"], value["progress"]
        row.last_checked_at = datetime.fromisoformat(value["last_checked_at"]) if value["last_checked_at"] else None
    sub.progress = deepcopy(checkpoint["progress"])

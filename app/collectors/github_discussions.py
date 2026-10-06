"""Prepare private GitHub PR/issue discussions, then explicitly apply a sealed preview."""
import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, TypeAdapter
from app.acquisition.common import ProbeError
from app.collectors.bundle import bytes_json, digest, private_write, read_json, clean_text, SENSITIVE
from app.collectors.client import apply_bundle, bundle_lock
from app.collectors.github import GitHubConfig, FILTER, stamp, github_token, matches, cleanup
from app.collectors.github_reader import RepositoryReader, Paused
from app.importers.github_discussions import (GitHubDiscussionEvidence, GitHubReviewPayload,
    DISCUSSION_OBJECTS, discussion_external_id, discussion_locator)
from app.schemas.collection_run import GitHubCollectorItem, GitHubRunCreate

PARSER = "github-discussions-rest-2026-03-10-v1"
FORMAT = "lifhop-github-discussions-preview-v1"
IDENTITY = r"repo:[1-9][0-9]{0,19}:(?:pull_request|issue|issue_comment|review|review_comment):[1-9][0-9]{0,19}"
EVIDENCE = TypeAdapter(GitHubDiscussionEvidence)


class DiscussionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=255)
    repository_id: int = Field(gt=0, lt=10**20)
    exclude_numbers: list[int] = Field(default_factory=list, max_length=1000)
    exclude_paths: list[str] = Field(default_factory=list, max_length=100)
    field_bytes: int = Field(default=65536, ge=256, le=65536)
    turn_bytes: int = Field(default=1048576, ge=4096, le=1048576)
    bundle_bytes: int = Field(default=268435456, ge=4096, le=536870912)
    max_pages: int = Field(default=1000, ge=1, le=10000)
    max_requests: int = Field(default=1000, ge=1, le=10000)
    run_seconds: int = Field(default=600, ge=1, le=1800)

    @field_validator("repository")
    @classmethod
    def valid_repository(cls, value):
        return GitHubConfig.valid_repository(value)

    @field_validator("exclude_paths")
    @classmethod
    def valid_paths(cls, value):
        return GitHubConfig.valid_paths(value)

    @field_validator("exclude_numbers")
    @classmethod
    def valid_numbers(cls, values):
        if any(value < 1 or value >= 10**20 for value in values):
            raise ValueError("Invalid excluded discussion number")
        return values


def load_config(path):
    return DiscussionConfig.model_validate(read_json(path, 65536))


def source_id(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value < 10**20:
        raise ValueError("Invalid source object ID")
    return value


def make_item(row, kind, cfg, parent=None, *, commits=None, commits_complete=True, extra_gaps=()):
    omissions = set(extra_gaps)
    user = row.get("user") or {}
    body = row.get("body")
    body_state = "unavailable" if body is None else "empty" if body == "" else "available"
    if body is not None and not isinstance(body, str):
        raise ValueError("Invalid source body")
    created = stamp(row.get("created_at"))
    submitted = stamp(row.get("submitted_at")) if kind == "review" else None
    updated = None if kind == "review" else stamp(row.get("updated_at"))
    event = submitted if kind == "review" else created
    if event is None or (kind != "review" and updated is None):
        omissions.add("DATE_UNAVAILABLE")
    def text(value):
        return clean_text(value, cfg, omissions)
    def sha(value):
        if value is None:
            return None
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{40}", value):
            omissions.add("FORMAT_UNSUPPORTED")
            return None
        return value
    data = dict(kind="github_" + kind, repository=cfg.repository, repository_id=cfg.repository_id,
        object_id=source_id(row["id"]), number=source_id(parent["number"] if parent else row["number"]),
        author=text(user.get("login"))[:255] if user.get("login") else None,
        author_id=source_id(user["id"]) if user.get("id") else None,
        body=text(body), body_state=body_state, created_at=created, updated_at=updated, filter_version=FILTER)
    if parent:
        data.update(parent_kind=parent["kind"], parent_id=parent["id"],
            parent_external_id=f"repo:{cfg.repository_id}:{parent['kind']}:{parent['id']}")
        title = f"{kind.replace('_', ' ').title()} on {'PR' if parent['kind'] == 'pull_request' else 'Issue'} #{parent['number']}"
    else:
        title = text(row.get("title"))[:255] or "Untitled discussion"
        labels = row.get("labels") or []
        if len(labels) > 100:
            omissions.add("ITEM_TRUNCATED")
        data.update(title=title, state=row["state"], state_reason=text(row.get("state_reason"))[:100] or None,
            labels=[text(label.get("name"))[:255] for label in labels[:100]], closed_at=stamp(row.get("closed_at")))
    if kind == "pull_request":
        data.update(merged=bool(row.get("merged")), draft=bool(row.get("draft")), merged_at=stamp(row.get("merged_at")),
            base_sha=sha((row.get("base") or {}).get("sha")), head_sha=sha((row.get("head") or {}).get("sha")),
            merge_sha=sha(row.get("merge_commit_sha")), commits=commits or [], commits_complete=commits_complete)
    if kind == "review":
        data.update(state=row["state"], submitted_at=submitted, commit_id=sha(row.get("commit_id")))
    if kind == "review_comment":
        path = row.get("path")
        excluded = path and (SENSITIVE.search(path) or matches(path, cfg.exclude_paths))
        if excluded:
            omissions.add("PATH_EXCLUDED")
        data.update(review_id=row.get("pull_request_review_id"), in_reply_to_id=row.get("in_reply_to_id"),
            path=None if excluded or not path else text(path),
            diff_hunk=None if excluded or row.get("diff_hunk") is None else text(row["diff_hunk"]),
            commit_id=sha(row.get("commit_id")), original_commit_id=sha(row.get("original_commit_id")))
        for key in ("line", "original_line", "start_line", "original_start_line", "side", "start_side"):
            data[key] = row.get(key)
    data["omissions"] = sorted(omissions)
    payload = EVIDENCE.validate_python(data)
    return GitHubCollectorItem(provider="github", source_scope=f"repo:{cfg.repository_id}",
        external_id=discussion_external_id(payload), title=title, event_at=event, source_updated_at=updated,
        parser_version=PARSER, completeness="partial" if omissions else "complete",
        locator=discussion_locator(payload), payload=payload)


class Preparation:
    def __init__(self, directory, cfg, reader):
        self.directory, self.cfg, self.reader = directory, cfg, reader
        self.state_path = directory / "preparation.json"
        if (directory / "manifest.json").exists():
            raise ProbeError("Preview already sealed; apply or use a new directory")
        if self.state_path.exists():
            self.state = read_json(self.state_path, 32 * 1024 * 1024)
            if (self.state["config_digest"] != digest(cfg.model_dump(mode="json")) or
                    self.state["parser_version"] != PARSER or self.state["filter_version"] != FILTER):
                raise ProbeError("Preparation config changed; use a new directory")
        else:
            self.state = dict(config_digest=digest(cfg.model_dump(mode="json")), parser_version=PARSER,
                filter_version=FILTER, client_run_uuid=str(uuid4()), started_at=datetime.now(timezone.utc).isoformat(),
                lists={kind:dict(page=1, done=False) for kind in ("pull_request", "issue")},
                roots=[], discovered={kind:[] for kind in ("pull_request","issue")},
                processed=[], stage=None, items=[], gaps=[], pages=0, excluded=0, retry_at=0, complete=False)
        self.state.setdefault("discovered", {kind:[root["id"] for root in self.state["roots"] if root["kind"] == kind]
            for kind in ("pull_request","issue")})
        self.reader.retry_at = self.state["retry_at"]
        authentication = "authenticated" if getattr(reader, "authenticated", False) else "anonymous"
        if self.state.get("rate_authentication", "anonymous") != authentication:
            self.reader.retry_at = self.state["retry_at"] = 0
        self.state["rate_authentication"] = authentication

    def save(self):
        if len(bytes_json(self.state)) > 32 * 1024 * 1024:
            raise Paused("SOURCE_LIMIT")
        private_write(self.state_path, self.state, replace=True)

    def gap(self, code):
        if code not in self.state["gaps"]:
            self.state["gaps"].append(code)

    def get(self, suffix, *, refresh=False):
        return self.reader.get(f"/repos/{self.cfg.repository}" + suffix, refresh=refresh)

    def page(self, suffix, page, *, refresh=False):
        if self.state["pages"] >= self.cfg.max_pages:
            raise Paused("PAGE_LIMIT")
        path = suffix + ("&" if "?" in suffix else "?") + f"per_page=100&page={page}"
        body, headers = self.get(path, refresh=refresh)
        if not isinstance(body, list):
            raise Paused("FORMAT_UNSUPPORTED")
        next_page = self.reader.next_page(headers, f"/repos/{self.cfg.repository}" + path)
        if next_page is not None and next_page <= page:
            raise Paused("SOURCE_CONFLICT")
        self.state["pages"] += 1
        return body, next_page

    def store(self, item, *, failed=None):
        stage = self.state["stage"]
        identity = item if failed else item.external_id
        target = stage["items"] if stage else self.state["items"]
        existing = next((row for row in target if row["external_id"] == identity), None)
        if existing:
            if not failed and existing["payload_digest"] != digest(item.model_dump(mode="json")):
                self.gap("MUTABLE_SOURCE_CHANGED")
            return
        if stage and any(row["external_id"] == identity for row in self.state["items"]):
            self.gap("SOURCE_CONFLICT")
            return
        if len(target) + (len(self.state["items"]) if stage else 0) >= 100000:
            raise Paused("RUN_LIMIT")
        if failed:
            self.gap(failed)
            row = dict(external_id=identity, file=None, payload_digest=digest({"external_id":identity,"error_code":"INVALID_ITEM"}), error_code="INVALID_ITEM")
        else:
            data = item.model_dump(mode="json")
            if len(bytes_json(data)) > self.cfg.turn_bytes:
                raise ValueError("Record exceeds configured item limit")
            size = sum(path.stat().st_size for path in self.directory.glob("item-*.json"))
            size += sum(path.stat().st_size for path in (self.directory / "cache").glob("*.json"))
            if size + len(bytes_json(data)) > self.cfg.bundle_bytes:
                raise Paused("SOURCE_LIMIT")
            file = "item-" + digest(identity) + ".json"
            # Only unsealed staged objects can be replaced after a mutable-source retry.
            private_write(self.directory/file, data, replace=(self.directory/file).exists())
            row = dict(external_id=identity, file=file, payload_digest=digest(data), error_code=None)
            for gap in item.payload.omissions:
                self.gap(gap)
        target.append(row)
        self.save()

    def record(self, row, kind, parent=None, **extra):
        try:
            identity = f"repo:{self.cfg.repository_id}:{kind}:{source_id(row['id'])}"
        except (ValueError, KeyError, TypeError):
            self.gap("FORMAT_UNSUPPORTED")
            return
        try:
            self.store(make_item(row, kind, self.cfg, parent, **extra))
        except (ValueError, KeyError, TypeError):
            self.store(identity, failed="INVALID_ITEM")

    def discover(self):
        for kind, endpoint in (("pull_request", "/pulls"), ("issue", "/issues")):
            cursor = self.state["lists"][kind]
            while not cursor["done"]:
                rows, next_page = self.page(endpoint + "?state=all&sort=created&direction=asc", cursor["page"])
                for row in rows:
                    if kind == "issue" and "pull_request" in row:
                        continue
                    try:
                        root = dict(kind=kind, id=source_id(row["id"]), number=source_id(row["number"]))
                    except (ValueError, KeyError, TypeError):
                        self.gap("FORMAT_UNSUPPORTED")
                        continue
                    found = self.state["discovered"][kind]
                    if root["id"] in found:
                        if any(previous["kind"] == kind and previous["id"] == root["id"] and previous != root for previous in self.state["roots"]):
                            self.gap("SOURCE_CONFLICT")
                        continue
                    if sum(len(ids) for ids in self.state["discovered"].values()) >= 100000:
                        raise Paused("SOURCE_LIMIT")
                    found.append(root["id"])
                    created = stamp(row.get("created_at"))
                    if root["number"] in self.cfg.exclude_numbers or (created and created > stamp(self.state["started_at"])):
                        self.state["excluded"] += 1
                        continue
                    if root not in self.state["roots"]:
                        if len(self.state["roots"]) >= 100000:
                            raise Paused("SOURCE_LIMIT")
                        self.state["roots"].append(root)
                cursor["done"] = next_page is None
                cursor["page"] = next_page or cursor["page"]
                self.save()

    def thread(self, root):
        suffix = f"/{'pulls' if root['kind'] == 'pull_request' else 'issues'}/{root['number']}"
        before, _ = self.get(suffix, refresh=True)
        if before.get("id") != root["id"] or before.get("number") != root["number"]:
            raise Paused("SOURCE_CONFLICT")
        stage = self.state["stage"]
        if stage is None:
            stage = dict(root=root, updated_at=before.get("updated_at"), retry=0, items=[], stream=0, page=1,
                commits=[], seen_commits=0, commits_complete=True)
            self.state["stage"] = stage
        if stage["root"] != root:
            raise ProbeError("Staged thread differs from preparation")
        if stage["updated_at"] != before.get("updated_at") and stage["retry"] == 0:
            self.reset_stage(before.get("updated_at"))
            stage = self.state["stage"]
        elif stage["updated_at"] != before.get("updated_at"):
            self.gap("MUTABLE_SOURCE_CHANGED")
        streams = [("issue_comment", f"/issues/{root['number']}/comments")]
        if root["kind"] == "pull_request":
            streams += [("review", suffix + "/reviews"), ("review_comment", suffix + "/comments"),
                ("commits", suffix + "/commits")]
        self.save()
        while stage["stream"] < len(streams):
            kind, endpoint = streams[stage["stream"]]
            try:
                rows, next_page = self.page(endpoint, stage["page"], refresh=True)
            except Paused as error:
                if error.code in {"AUTH_FAILED", "ACCESS_DENIED", "REF_UNAVAILABLE", "SSO_REQUIRED", "READ_FAILED", "TIMEOUT"}:
                    self.gap(error.code)
                    if kind == "commits":
                        stage["commits_complete"] = False
                    stage["stream"] += 1
                    stage["page"] = 1
                    self.save()
                    continue
                raise
            for row in rows:
                if kind == "commits":
                    value = row.get("sha")
                    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{40}", value):
                        self.gap("FORMAT_UNSUPPORTED")
                        stage["commits_complete"] = False
                    elif value not in stage["commits"]:
                        stage["seen_commits"] += 1
                        if len(stage["commits"]) < 250:
                            stage["commits"].append(value)
                else:
                    self.record(row, kind, root)
            if next_page is None:
                stage["stream"] += 1
                stage["page"] = 1
            else:
                stage["page"] = next_page
            self.save()
        after, _ = self.get(suffix, refresh=True)
        if after.get("id") != root["id"] or after.get("number") != root["number"]:
            raise Paused("SOURCE_CONFLICT")
        if stage["updated_at"] != after.get("updated_at") and stage["retry"] == 0:
            self.reset_stage(after.get("updated_at"))
            return self.thread(root)
        omissions = []
        if stage["retry"] > 1 or stage["updated_at"] != after.get("updated_at"):
            omissions.append("MUTABLE_SOURCE_CHANGED")
        if root["kind"] == "pull_request":
            if after.get("commits") != len(stage["commits"]) or stage["seen_commits"] > 250 or not stage["commits_complete"]:
                stage["commits_complete"] = False
                omissions.append("PR_COMMIT_MEMBERSHIP_INCOMPLETE")
        self.record(after, root["kind"], commits=stage["commits"], commits_complete=stage["commits_complete"], extra_gaps=omissions)
        self.state["items"].extend(stage["items"])
        self.state["processed"].append(f"{root['kind']}:{root['id']}")
        self.state["stage"] = None
        self.save()

    def reset_stage(self, updated):
        stage = self.state["stage"]
        # Delete only this unsealed stage's recognized payloads; never completed threads.
        for row in stage["items"]:
            if row["file"]:
                if not re.fullmatch(r"item-[a-f0-9]{64}\.json", row["file"]):
                    raise ProbeError("Invalid staged payload path")
                (self.directory / row["file"]).unlink(missing_ok=True)
        stage.update(updated_at=updated, retry=stage["retry"] + 1, items=[], stream=0, page=1,
            commits=[], seen_commits=0, commits_complete=True)
        self.save()

    def run(self):
        repo, _ = self.get("", refresh=True)
        if repo.get("id") != self.cfg.repository_id:
            raise Paused("SOURCE_CONFLICT")
        self.discover()
        for root in self.state["roots"]:
            if f"{root['kind']}:{root['id']}" in self.state["processed"]:
                continue
            try:
                self.thread(root)
            except Paused as error:
                if error.code not in {"AUTH_FAILED", "ACCESS_DENIED", "REF_UNAVAILABLE", "SSO_REQUIRED", "READ_FAILED", "TIMEOUT"}:
                    raise
                self.gap(error.code)
                if self.state["stage"]:
                    self.state["items"].extend(self.state["stage"]["items"])
                self.state["stage"] = None
                self.state["processed"].append(f"{root['kind']}:{root['id']}")
                self.save()
        self.state["complete"] = True
        self.save()

    def seal(self, partial=False):
        if not self.state["complete"] and not partial:
            raise ProbeError("Preparation incomplete; resume or explicitly seal partial")
        if not self.state["complete"]:
            self.gap("PREPARATION_INCOMPLETE")
        items = self.state["items"] + (self.state["stage"]["items"] if self.state["stage"] else [])
        counts = {kind: 0 for kind in DISCUSSION_OBJECTS}
        for row in items:
            counts[row["external_id"].split(":")[2]] += 1
        coverage = dict(repository=self.cfg.repository, repository_id=self.cfg.repository_id, branches=[], commits=0,
            documents=0, head_documents=[], lower_bound=bool(self.state["gaps"]) or not self.state["complete"],
            gaps=sorted(self.state["gaps"]), discussions=dict(records=counts,
                discovered_pull_requests=len(self.state["discovered"]["pull_request"]),
                discovered_issues=len(self.state["discovered"]["issue"]),
                walk_complete=self.state["complete"] and not any(gap in {"AUTH_FAILED","ACCESS_DENIED","REF_UNAVAILABLE",
                    "SSO_REQUIRED","READ_FAILED","TIMEOUT","FORMAT_UNSUPPORTED","SOURCE_CONFLICT","PAGE_LIMIT",
                    "RUN_LIMIT","SOURCE_LIMIT","PREPARATION_INCOMPLETE"} for gap in self.state["gaps"]),
                snapshot_atomic=False, started_at=self.state["started_at"],
                finished_at=datetime.now(timezone.utc).isoformat(),
                failed=sum(row["error_code"] is not None for row in items), excluded=self.state["excluded"]))
        manifest = dict(bundle_format=FORMAT, client_run_uuid=self.state["client_run_uuid"], provider="github",
            scope=f"repo:{self.cfg.repository_id}", config_digest=self.state["config_digest"], parser_version=PARSER,
            filter_version=FILTER, expected_items=len(items), items=items, coverage=coverage)
        manifest["manifest_digest"] = digest(manifest)
        GitHubRunCreate.model_validate(run_data(manifest))
        links = []
        for row in items:
            if row["file"]:
                item = read_json(self.directory/row["file"], self.cfg.turn_bytes)
                links.append(f'<li><a href="{row["file"]}">{html.escape(item["title"])}</a><pre>{html.escape(json.dumps(item["payload"],ensure_ascii=False,indent=2))}</pre></li>')
        report = '<!doctype html><html lang="en"><meta charset="utf-8"><title>GitHub discussions preview</title><h1>GitHub discussions preview</h1><p>Private sanitized preview. Snapshot collected over a time window. Review before apply. No AI calls.</p><pre>' + html.escape(json.dumps(coverage,indent=2)) + '</pre><ul>' + ''.join(links) + '</ul>'
        private_write(self.directory/"preview.html", report.encode(), replace=True)
        private_write(self.directory/"manifest.json", manifest)
        validate_bundle(self.directory, self.cfg)
        return manifest


def run_data(manifest):
    return {key: manifest[key] for key in ("client_run_uuid", "provider", "scope", "manifest_digest", "parser_version", "filter_version", "expected_items", "coverage")}


def validate_bundle(directory, cfg):
    manifest = read_json(directory/"manifest.json", 32 * 1024 * 1024)
    check = dict(manifest)
    expected = check.pop("manifest_digest")
    if digest(check) != expected or manifest["bundle_format"] != FORMAT or manifest["config_digest"] != digest(cfg.model_dump(mode="json")):
        raise ProbeError("Preview/config integrity mismatch")
    if manifest["parser_version"] != PARSER or manifest["filter_version"] != FILTER or manifest["scope"] != f"repo:{cfg.repository_id}":
        raise ProbeError("Unsupported preview or repository identity")
    GitHubRunCreate.model_validate(run_data(manifest))
    counts = {kind: 0 for kind in DISCUSSION_OBJECTS}
    identities = set()
    for row in manifest["items"]:
        identity = row["external_id"]
        if identity in identities or not re.fullmatch(IDENTITY, identity) or not identity.startswith(manifest["scope"] + ":"):
            raise ProbeError("Duplicate or invalid discussion identity")
        identities.add(identity)
        counts[identity.split(":")[2]] += 1
        if not re.fullmatch(r"[a-f0-9]{64}", row["payload_digest"]):
            raise ProbeError("Invalid payload digest")
        if row["file"] is None:
            if row["error_code"] != "INVALID_ITEM" or row["payload_digest"] != digest({"external_id":identity,"error_code":"INVALID_ITEM"}):
                raise ProbeError("Invalid body-free outcome")
            continue
        if row["error_code"] is not None or not re.fullmatch(r"item-[a-f0-9]{64}\.json", row["file"]):
            raise ProbeError("Invalid payload path")
        data = read_json(directory/row["file"], cfg.turn_bytes)
        item = GitHubCollectorItem.model_validate(data)
        if (item.external_id != identity or item.source_scope != manifest["scope"] or item.payload.repository != cfg.repository
                or digest(data) != row["payload_digest"] or item.parser_version != PARSER or item.payload.filter_version != FILTER):
            raise ProbeError("Preview body changed")
    if len(identities) != manifest["expected_items"] or counts != manifest["coverage"]["discussions"]["records"]:
        raise ProbeError("Manifest discussion counts differ")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init-config", "prepare", "seal", "apply", "cleanup"])
    parser.add_argument("--config", type=Path, default=Path(".local/github-discussions-collector.json"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--repository", default="moonkongv2/jy_yamyam")
    parser.add_argument("--github-cli-auth", action="store_true")
    parser.add_argument("--partial", action="store_true")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--email")
    args = parser.parse_args()
    try:
        directory = args.run_dir.expanduser().absolute()
        if directory.is_symlink() or any(parent.is_symlink() for parent in directory.parents):
            raise ProbeError("Symlink output directories are not allowed")
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        directory.chmod(0o700)
        if args.action == "init-config":
            cfg = DiscussionConfig(repository=args.repository, repository_id=1)
            repo, _ = RepositoryReader(directory/"cache", cfg, github_token(args.github_cli_auth)).get(f"/repos/{cfg.repository}", refresh=True)
            cfg.repository_id = source_id(repo["id"])
            private_write(args.config, cfg.model_dump(mode="json"))
            print(json.dumps({"state":"config created", "repository_id":cfg.repository_id, "config":str(args.config)}))
            return
        cfg = load_config(args.config)
        if args.action == "cleanup":
            print(json.dumps({"state":"cleaned", "removed_files":cleanup(directory, cfg)}))
            return
        if args.action == "apply":
            if not args.email:
                raise ProbeError("--email is required")
            result = apply_bundle(directory, cfg, args.api_url, args.email, validator=validate_bundle,
                item_type=GitHubCollectorItem, run_type=GitHubRunCreate)
            print(json.dumps({"state":result["status"], "run_id":result["id"], "counts":result["counts"]}))
            return
        with bundle_lock(directory):
            reader = RepositoryReader(directory/"cache", cfg, github_token(args.github_cli_auth) if args.action == "prepare" else None)
            prep = Preparation(directory, cfg, reader)
            if args.action == "prepare":
                try:
                    prep.run()
                except Paused as error:
                    if error.code in {"AUTH_FAILED", "ACCESS_DENIED", "REF_UNAVAILABLE", "SSO_REQUIRED", "READ_FAILED", "TIMEOUT"}:
                        prep.gap(error.code)
                    prep.state["retry_at"] = error.retry_at
                    prep.save()
                    print(json.dumps({"state":"paused", "reason":error.code, "retry_at":error.retry_at,
                        "prepared_items":len(prep.state["items"]), "resume":"Re-run the same prepare command"}))
                    return
            result = prep.seal(args.partial)
            print(json.dumps({"state":"preview ready", "items":result["expected_items"], "coverage":result["coverage"], "report":str(directory/"preview.html")}))
    except (ProbeError, ValueError, KeyError, OSError, TypeError) as error:
        print(json.dumps({"state":"failed", "error":str(error) if isinstance(error,ProbeError) else type(error).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()

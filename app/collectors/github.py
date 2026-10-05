"""Private resumable GitHub preparation, reviewed preview and explicit apply."""
import argparse
import base64
import fnmatch
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.acquisition.common import ProbeError
from app.collectors.bundle import bytes_json, digest, private_write, read_json, clean_text, SENSITIVE
from app.collectors.client import apply_bundle, bundle_lock
from app.collectors.github_reader import RepositoryReader, Paused
from app.importers.canonical import GitHubCommitPayload, GitHubDocumentPayload, github_external_id
from app.schemas.collection_run import GitHubCollectorItem, GitHubRunCreate

PARSER = "github-rest-2026-03-10-v1"
FILTER = "github-local-filter-v1"
FORMAT = "lifhop-github-preview-v1"


class GitHubConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    repository_id: int = Field(gt=0)
    branches: list[str] = Field(default_factory=lambda: ["main"], min_length=1, max_length=100)
    documents: list[str] = Field(default_factory=lambda: ["README.md", "ROADMAP.md", "DECISIONS.md", "docs/**/*.md"], max_length=100)
    exclude_paths: list[str] = Field(default_factory=list, max_length=100)
    field_bytes: int = Field(default=65536, ge=256, le=65536)
    turn_bytes: int = Field(default=1048576, ge=4096, le=1048576)
    document_bytes: int = Field(default=1048576, ge=256, le=1048576)
    bundle_bytes: int = Field(default=268435456, ge=4096, le=536870912)
    max_pages: int = Field(default=1000, ge=1, le=10000)
    max_requests: int = Field(default=1000, ge=1, le=10000)
    run_seconds: int = Field(default=600, ge=1, le=1800)

    @field_validator("branches")
    @classmethod
    def valid_branches(cls, values):
        if any(not p or len(p)>255 or any(ord(c)<32 for c in p) for p in values):
            raise ValueError("Invalid branch name")
        return values

    @field_validator("repository")
    @classmethod
    def valid_repository(cls, value):
        if any(p in {".",".."} for p in value.split("/")):
            raise ValueError("Invalid repository name")
        return value

    @field_validator("documents", "exclude_paths")
    @classmethod
    def valid_paths(cls, values):
        if any(not p or p.startswith("/") or "\\" in p or any(part in {"", ".", ".."} for part in p.split("/")) or any(ord(c)<32 for c in p) for p in values):
            raise ValueError("Paths must be relative patterns without parent traversal")
        return values


def load_config(path):
    return GitHubConfig.model_validate(read_json(path, 65536))


def matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, p) or fnmatch.fnmatchcase(path, p.replace("**/", "")) for p in patterns)


def allowed(path, cfg):
    return not SENSITIVE.search(path) and not matches(path, cfg.exclude_paths)


def stamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def make_item(payload, cfg, date, title):
    url = "https://github.com/" + cfg.repository
    locator = url + "/commit/" + payload.sha if isinstance(payload, GitHubCommitPayload) else url + "/blob/" + payload.sha + "/" + quote(payload.path, safe="/")
    return GitHubCollectorItem(provider="github", source_scope=f"repo:{cfg.repository_id}",
        external_id=github_external_id(payload), title=title[:255] or "GitHub record", event_at=date,
        source_updated_at=date, parser_version=PARSER, completeness="partial" if payload.omissions else "complete",
        locator=locator, payload=payload)


class Preparation:
    def __init__(self, directory, cfg, reader):
        self.directory, self.cfg, self.reader = directory, cfg, reader
        self.state_path = directory / "preparation.json"
        if self.state_path.exists():
            self.state = read_json(self.state_path, 32*1024*1024)
            if self.state["config_digest"] != digest(cfg.model_dump(mode="json")) or self.state.get("parser_version") != PARSER or self.state.get("filter_version") != FILTER:
                raise ProbeError("Preparation config changed; create a new run directory")
        else:
            self.state = dict(config_digest=digest(cfg.model_dump(mode="json")), parser_version=PARSER, filter_version=FILTER, client_run_uuid=str(uuid4()),
                branches=[], commits=[], items=[], processed=[], documents=[], head_documents=[], gaps=[], retry_at=0,
                heads_done=[], complete=False)
        self.reader.retry_at = self.state["retry_at"]

    def save(self):
        if len(bytes_json(self.state)) > 32 * 1024 * 1024:
            raise Paused("SOURCE_LIMIT")
        private_write(self.state_path, self.state, replace=True)

    def gap(self, code):
        if code not in self.state["gaps"]:
            self.state["gaps"].append(code)

    def store(self, item):
        data = item.model_dump(mode="json")
        identity = item.external_id
        if any(r["external_id"] == identity for r in self.state["items"]):
            return
        if len(self.state["items"]) >= 100000:
            raise Paused("RUN_LIMIT")
        file = "item-" + digest(identity) + ".json"
        raw = bytes_json(data)
        cached = sum(p.stat().st_size for p in (self.directory/"cache").glob("*.json"))
        if cached + sum((self.directory/r["file"]).stat().st_size for r in self.state["items"] if r["file"]) + len(raw) > self.cfg.bundle_bytes:
            raise Paused("SOURCE_LIMIT")
        path = self.directory / file
        # Recovery after body write but before journal advancement is idempotent.
        if path.exists():
            if path.read_bytes() != raw:
                raise ProbeError("Prepared body differs from journal recovery")
        else:
            private_write(path, raw)
        self.state["items"].append(dict(external_id=identity, file=file, payload_digest=digest(data), error_code=None))
        self.save()

    def get(self, suffix):
        return self.reader.get(f"/repos/{self.cfg.repository}" + suffix)

    def invalid(self, identity, code):
        self.gap(code)
        if not any(r["external_id"] == identity for r in self.state["items"]):
            self.state["items"].append(dict(external_id=identity, file=None,
                payload_digest=digest({"external_id":identity,"error_code":"INVALID_ITEM"}), error_code="INVALID_ITEM"))
        self.save()

    def run(self):
        repo, _ = self.get("")
        if repo["id"] != self.cfg.repository_id:
            raise ProbeError("Repository ID changed; do not reuse this source")
        inventory, headers = self.get("/branches?per_page=100&page=1")
        if not isinstance(inventory, list):
            raise Paused("FORMAT_UNSUPPORTED")
        if not inventory and not headers.get("link"):
            self.state["complete"] = True
            self.save()
            return
        for name in dict.fromkeys(self.cfg.branches):
            branch = next((b for b in self.state["branches"] if b["name"] == name), None)
            if branch is None:
                head, _ = self.get("/branches/" + quote(name, safe=""))
                branch = dict(name=name, head_sha=head["commit"]["sha"], page=1, walk_complete=False, shas=[])
                self.state["branches"].append(branch)
                self.save()
            while not branch["walk_complete"]:
                if branch["page"] > self.cfg.max_pages:
                    raise Paused("PAGE_LIMIT")
                suffix = f"/commits?sha={branch['head_sha']}&per_page=100&page={branch['page']}"
                rows, headers = self.get(suffix)
                if not isinstance(rows, list):
                    raise Paused("FORMAT_UNSUPPORTED")
                for row in rows:
                    sha = row["sha"]
                    if sha not in branch["shas"]:
                        branch["shas"].append(sha)
                    if sha not in self.state["commits"]:
                        if len(self.state["commits"]) >= 100000:
                            raise Paused("RUN_LIMIT")
                        if not re.fullmatch(r"[a-f0-9]{40}", sha):
                            raise Paused("FORMAT_UNSUPPORTED")
                        self.state["commits"].append(sha)
                next_page = self.reader.next_page(headers, f"/repos/{self.cfg.repository}" + suffix)
                if next_page is not None and next_page <= branch["page"]:
                    raise Paused("SOURCE_CONFLICT")
                branch["walk_complete"] = next_page is None
                branch["page"] = next_page or branch["page"]
                self.save()
        for sha in self.state["commits"]:
            if sha in self.state["processed"]:
                continue
            try:
                self.commit(sha)
            except Paused as error:
                if error.code != "INVALID_ITEM":
                    raise
                self.invalid(f"repo:{self.cfg.repository_id}:commit:{sha}", "INVALID_ITEM")
            except (ValueError, KeyError, TypeError):
                self.invalid(f"repo:{self.cfg.repository_id}:commit:{sha}", "INVALID_ITEM")
            self.state["processed"].append(sha)
            self.save()
        for branch in self.state["branches"]:
            sha = branch["head_sha"]
            if sha in self.state["heads_done"]:
                continue
            commit, _ = self.get(f"/commits/{sha}?per_page=100&page=1")
            for path, blob in self.tree_documents(commit["commit"]["tree"]["sha"]):
                candidates = [d for d in self.state["documents"] if d["path"] == path and d["blob_sha"] == blob and d["sha"] in branch["shas"]]
                existing = min(candidates, key=lambda d: branch["shas"].index(d["sha"])) if candidates else None
                identity = existing["external_id"] if existing else self.document(commit, path, "head_baseline")
                if identity:
                    mapping = dict(head_sha=sha, path=path, external_id=identity)
                    if mapping not in self.state["head_documents"]:
                        self.state["head_documents"].append(mapping)
            self.state["heads_done"].append(sha)
            self.save()
        self.state["complete"] = True
        self.save()

    def tree_documents(self, tree_sha, prefix=""):
        tree, _ = self.get("/git/trees/" + tree_sha)
        if tree.get("truncated"):
            self.gap("TREE_TRUNCATED")
        for row in tree["tree"]:
            path = prefix + row["path"]
            if not allowed(path, self.cfg):
                continue
            if row["mode"] == "040000" and any(p.startswith(path+"/") or path.startswith(p.split("*")[0].rsplit("/", 1)[0]+"/") or p.startswith("*") for p in self.cfg.documents):
                yield from self.tree_documents(row["sha"], path+"/")
            elif matches(path, self.cfg.documents):
                if row["mode"] in {"100644", "100755"}:
                    yield path, row["sha"]
                else:
                    self.gap("DOCUMENT_TYPE_OMITTED")

    def leaf(self, tree_sha, path):
        parts = path.split("/")
        for index, part in enumerate(parts):
            tree, _ = self.get("/git/trees/" + tree_sha)
            if tree.get("truncated"):
                self.gap("TREE_TRUNCATED")
            row = next((r for r in tree["tree"] if r["path"] == part), None)
            if row is None or row["mode"] not in {"040000", "100644", "100755"}:
                return None
            if index < len(parts)-1 and row["mode"] != "040000":
                return None
            tree_sha = row["sha"]
        return row if row["mode"] in {"100644", "100755"} else None

    def document(self, commit, path, reason):
        if not allowed(path, self.cfg) or not matches(path, self.cfg.documents):
            return None
        try:
            leaf = self.leaf(commit["commit"]["tree"]["sha"], path)
            if not leaf:
                self.gap("DOCUMENT_TYPE_OMITTED")
                return None
            obj, _ = self.get("/contents/" + quote(path, safe="/") + "?ref=" + commit["sha"])
            if obj.get("type") != "file" or obj.get("encoding") != "base64" or obj.get("sha") != leaf["sha"]:
                self.gap("DOCUMENT_TYPE_OMITTED")
                return None
            if obj.get("size", self.cfg.document_bytes+1) > self.cfg.document_bytes:
                self.gap("DOCUMENT_SIZE_LIMIT")
                return None
            content = base64.b64decode("".join(obj["content"].split()), validate=True)
            if len(content) > self.cfg.document_bytes:
                self.gap("DOCUMENT_SIZE_LIMIT")
                return None
            text = content.decode("utf-8")
            if text.startswith("version https://git-lfs.github.com/spec/") or "\x00" in text:
                self.gap("DOCUMENT_TYPE_OMITTED")
                return None
            omissions = set()
            text = clean_text(text, self.cfg.model_copy(update={"field_bytes":self.cfg.document_bytes}), omissions)
            payload = GitHubDocumentPayload(repository_id=self.cfg.repository_id, repository=self.cfg.repository,
                sha=commit["sha"], blob_sha=obj["sha"], path=path, content=text, snapshot_reason=reason,
                omissions=sorted(omissions), filter_version=FILTER)
            item = make_item(payload, self.cfg, stamp((commit["commit"].get("committer") or {}).get("date")), f"{path} at {commit['sha'][:10]}")
            self.store(item)
            if not any(d["external_id"] == item.external_id for d in self.state["documents"]):
                self.state["documents"].append(dict(path=path, blob_sha=obj["sha"], sha=commit["sha"], external_id=item.external_id))
            for code in omissions:
                self.gap(code)
            self.save()
            return item.external_id
        except Paused as error:
            if error.code != "REF_UNAVAILABLE":
                raise
            self.gap("DOCUMENT_UNAVAILABLE")
        except (UnicodeDecodeError, ValueError, KeyError):
            import hashlib
            self.invalid(f"repo:{self.cfg.repository_id}:document:{commit['sha']}:{hashlib.sha256(path.encode()).hexdigest()}", "DOCUMENT_INVALID")
        return None

    def commit(self, sha):
        first = None
        files, page, omissions = [], 1, set()
        seen_paths = set()
        retained_bytes = 0
        while True:
            suffix = f"/commits/{sha}?per_page=100&page={page}"
            body, headers = self.get(suffix)
            if body["sha"] != sha:
                raise Paused("SOURCE_CONFLICT")
            if first is None:
                first = body
            elif body["commit"] != first["commit"] or body["parents"] != first["parents"]:
                raise Paused("SOURCE_CONFLICT")
            for row in body.get("files", []):
                path = row["filename"]
                if path in seen_paths:
                    raise Paused("SOURCE_CONFLICT")
                seen_paths.add(path)
                if not allowed(path, self.cfg):
                    omissions.add("PATH_EXCLUDED")
                    continue
                patch = row.get("patch")
                state = "available" if isinstance(patch, str) else "unavailable"
                if state == "unavailable":
                    omissions.add("PATCH_UNAVAILABLE")
                clean = clean_text(patch, self.cfg, omissions) if patch is not None else None
                if clean != patch and patch is not None:
                    state = "partial"
                file = dict(path=path, previous_path=row.get("previous_filename"), status=row["status"],
                    additions=row.get("additions",0), deletions=row.get("deletions",0), patch=clean, patch_state=state)
                if file["previous_path"] and not allowed(file["previous_path"], self.cfg):
                    file["previous_path"] = None
                    omissions.add("PATH_EXCLUDED")
                size = len(bytes_json(file))
                # Keep memory bounded while still discovering every selected document.
                if retained_bytes + size <= self.cfg.turn_bytes // 2:
                    files.append(file)
                    retained_bytes += size
                else:
                    omissions.add("ITEM_TRUNCATED")
                if row["status"] != "removed" and matches(path, self.cfg.documents):
                    self.document(first, path, "historical_change")
            next_page = self.reader.next_page(headers, f"/repos/{self.cfg.repository}"+suffix)
            if not next_page:
                break
            if next_page <= page:
                raise Paused("SOURCE_CONFLICT")
            if next_page > self.cfg.max_pages or len(seen_paths) >= 3000:
                omissions.add("FILE_PAGE_LIMIT")
                break
            page = next_page
        if len(seen_paths) >= 3000:
            omissions.add("FILE_PAGE_LIMIT")
        commit = first["commit"]
        if stamp((commit.get("committer") or {}).get("date")) is None:
            omissions.add("DATE_UNAVAILABLE")
        payload = GitHubCommitPayload(repository_id=self.cfg.repository_id, repository=self.cfg.repository,
            sha=sha, tree_sha=commit["tree"]["sha"], message=clean_text(commit["message"],self.cfg,omissions),
            author={k:clean_text((commit.get("author") or {}).get(k),self.cfg,omissions) for k in ("name","email","date")},
            committer={k:clean_text((commit.get("committer") or {}).get(k),self.cfg,omissions) for k in ("name","email","date")},
            parents=[p["sha"] for p in first["parents"]], files=files, omissions=sorted(omissions), filter_version=FILTER)
        # Bound the searchable record without losing separately discovered documents.
        while True:
            try:
                item = make_item(payload,self.cfg,stamp((commit.get("committer") or {}).get("date")),payload.message.splitlines()[0] if payload.message else "GitHub commit")
                if len(bytes_json(item.model_dump(mode="json"))) > self.cfg.turn_bytes:
                    raise ValueError("item size")
                break
            except ValueError:
                if not payload.files:
                    raise Paused("INVALID_ITEM") from None
                payload.files.pop()
                payload.omissions = sorted(set(payload.omissions) | {"ITEM_TRUNCATED"})
        self.store(item)
        for gap in payload.omissions:
            self.gap(gap)

    def seal(self, partial=False):
        if (self.directory/"manifest.json").exists():
            raise FileExistsError("Preview already sealed")
        if not self.state["complete"] and not partial:
            raise ProbeError("Preparation incomplete; resume or explicitly seal partial")
        if not self.state["complete"]:
            self.gap("PREPARATION_INCOMPLETE")
        branches = [dict(name=b["name"],head_sha=b["head_sha"],walk_complete=b["walk_complete"],commits=len(b["shas"])) for b in self.state["branches"]]
        manifest = dict(bundle_format=FORMAT, client_run_uuid=self.state["client_run_uuid"], provider="github",
            scope=f"repo:{self.cfg.repository_id}", config_digest=self.state["config_digest"], parser_version=PARSER,
            filter_version=FILTER, expected_items=len(self.state["items"]), items=self.state["items"],
            coverage=dict(repository=self.cfg.repository,repository_id=self.cfg.repository_id,branches=branches,
                commits=len(self.state["processed"]),documents=len({d['external_id'] for d in self.state['documents']}),
                lower_bound=not self.state["complete"] or bool(self.state["gaps"]),gaps=sorted(self.state["gaps"]),head_documents=self.state["head_documents"]))
        manifest["manifest_digest"] = digest(manifest)
        GitHubRunCreate.model_validate({key: manifest[key] for key in ("client_run_uuid", "provider", "scope", "manifest_digest", "parser_version", "filter_version", "expected_items", "coverage")})
        links = "".join(f'<li><a href="{r["file"]}">{html.escape(read_json(self.directory/r["file"], self.cfg.turn_bytes)["title"])}</a> — {html.escape(r["external_id"])}</li>' for r in manifest["items"] if r["file"])
        report = '<!doctype html><html lang="en"><meta charset="utf-8"><title>GitHub backfill preview</title><h1>GitHub backfill preview</h1><p>Private sanitized preview. Review exact linked JSON before apply. No AI calls.</p><pre>'+html.escape(json.dumps(manifest["coverage"],indent=2))+'</pre><ul>'+links+'</ul>'
        private_write(self.directory/"preview.html",report.encode(),replace=True)
        private_write(self.directory/"manifest.json",manifest)
        return manifest


def validate_bundle(directory, cfg):
    manifest = read_json(directory/"manifest.json",32*1024*1024)
    check = dict(manifest)
    expected = check.pop("manifest_digest")
    if digest(check) != expected or manifest["bundle_format"] != FORMAT or manifest["config_digest"] != digest(cfg.model_dump(mode="json")):
        raise ProbeError("Preview/config integrity mismatch")
    if manifest["parser_version"] != PARSER or manifest["filter_version"] != FILTER or manifest["scope"] != f"repo:{cfg.repository_id}":
        raise ProbeError("Unsupported preview or repository identity")
    GitHubRunCreate.model_validate({key: manifest[key] for key in ("client_run_uuid", "provider", "scope", "manifest_digest", "parser_version", "filter_version", "expected_items", "coverage")})
    identities = set()
    for row in manifest["items"]:
        file = row["file"]
        if row["external_id"] in identities:
            raise ProbeError("Duplicate identity or invalid payload path")
        identities.add(row["external_id"])
        if file is None:
            if row["error_code"] != "INVALID_ITEM" or not re.fullmatch(r"repo:"+str(cfg.repository_id)+r":(?:commit:[a-f0-9]{40}|document:[a-f0-9]{40}:[a-f0-9]{64})",row["external_id"]):
                raise ProbeError("Invalid body-free outcome")
            continue
        if row["error_code"] is not None or not re.fullmatch(r"item-[a-f0-9]{64}\.json",file):
            raise ProbeError("Invalid payload path")
        data = read_json(directory/file,cfg.turn_bytes)
        item = GitHubCollectorItem.model_validate(data)
        if item.external_id != row["external_id"] or item.source_scope != manifest["scope"] or digest(data) != row["payload_digest"] or item.parser_version != PARSER or item.payload.filter_version != FILTER:
            raise ProbeError("Preview body changed")
    if manifest["expected_items"] != len(identities):
        raise ProbeError("Manifest count mismatch")
    return manifest


def cleanup(directory, cfg):
    """Explicitly remove only recognized files; refuse unrelated data or symlinks."""
    with bundle_lock(directory):
        state = read_json(directory/"preparation.json", 32*1024*1024)
        if state["config_digest"] != digest(cfg.model_dump(mode="json")):
            raise ProbeError("Cleanup config does not match preparation")
        known = {"preparation.json", "manifest.json", "preview.html", "checkpoint.json", ".apply.lock", "cache"}
        files = []
        for path in directory.iterdir():
            if path.is_symlink() or (path.name not in known and not re.fullmatch(r"item-[a-f0-9]{64}\.json",path.name)):
                raise ProbeError("Cleanup refused unknown files or symlinks")
            if path.name == "cache":
                for cache in path.iterdir():
                    if cache.is_symlink() or not cache.is_file() or not re.fullmatch(r"[a-f0-9]{64}\.json",cache.name):
                        raise ProbeError("Cleanup refused unknown cache files")
                    files.append(cache)
            elif path.name != ".apply.lock":
                if not path.is_file():
                    raise ProbeError("Cleanup refused non-file input")
                files.append(path)
        for path in files:
            path.unlink()
        if (directory/"cache").exists():
            (directory/"cache").rmdir()
        return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["init-config","prepare","seal","apply","cleanup"])
    parser.add_argument("--config",type=Path,default=Path(".local/github-collector.json"))
    parser.add_argument("--repository",default="moonkongv2/jy_yamyam")
    parser.add_argument("--branch",action="append")
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--partial",action="store_true")
    parser.add_argument("--api-url",default="http://localhost:8000")
    parser.add_argument("--email")
    args = parser.parse_args()
    try:
        directory = args.run_dir.expanduser().absolute()
        if directory.is_symlink() or any(parent.is_symlink() for parent in directory.parents):
            raise ProbeError("Symlink output directories are not allowed")
        directory.mkdir(parents=True,mode=0o700,exist_ok=True)
        directory.chmod(0o700)
        if args.action == "init-config":
            cfg = GitHubConfig(repository=args.repository,repository_id=1,branches=args.branch or ["main"])
            reader = RepositoryReader(directory/"cache",cfg,os.environ.get("GITHUB_TOKEN"))
            repo,_ = reader.get(f"/repos/{cfg.repository}")
            cfg.repository_id = repo["id"]
            private_write(args.config,cfg.model_dump(mode="json"))
            print(json.dumps({"state":"config created","repository_id":cfg.repository_id,"config":str(args.config)}))
            return
        cfg = load_config(args.config)
        if args.action == "cleanup":
            print(json.dumps({"state":"cleaned", "removed_files":cleanup(directory,cfg)}))
            return
        if args.action == "apply":
            if not args.email:
                raise ProbeError("--email is required")
            result = apply_bundle(directory,cfg,args.api_url,args.email,validator=validate_bundle,
                item_type=GitHubCollectorItem,run_type=GitHubRunCreate)
            print(json.dumps({"state":result["status"],"run_id":result["id"],"counts":result["counts"]}))
            return
        if (directory/"manifest.json").exists():
            raise ProbeError("Preview already sealed; apply it or choose a new directory")
        with bundle_lock(directory):
            prep = Preparation(directory,cfg,RepositoryReader(directory/"cache",cfg,os.environ.get("GITHUB_TOKEN")))
            if args.action == "prepare":
                try:
                    prep.run()
                except Paused as error:
                    prep.state["retry_at"] = error.retry_at
                    prep.save()
                    print(json.dumps({"state":"paused","reason":error.code,"retry_at":error.retry_at,
                        "prepared_items":len(prep.state["items"]),"resume":"Re-run the same prepare command"}))
                    return
            result = prep.seal(args.partial)
            print(json.dumps({"state":"preview ready","items":result["expected_items"],"coverage":result["coverage"],"report":str(directory/"preview.html")}))
    except (ProbeError, ValueError, KeyError, OSError, TypeError) as error:
        print(json.dumps({"state":"failed","error":str(error) if isinstance(error,ProbeError) else type(error).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()

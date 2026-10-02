import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.acquisition.common import ProbeError, preview

API_VERSION = "2026-03-10"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_BYTES = 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Redirects can reflect renames; don't forward credentials to another host.
        return None


class GitHubReader:
    def __init__(self, token: str | None = None):
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())
        self.access = []

    def get(self, path: str) -> tuple[object, dict]:
        if not path.startswith("/repos/") or any(c in path for c in ("\n", "\r")):
            raise ProbeError("Only repository GET endpoints are allowed.")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION,
                   "User-Agent": "lifhop-acquisition-probe"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request("https://api.github.com" + path, headers=headers, method="GET")
        try:
            with self.opener.open(request, timeout=20) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ProbeError("GitHub response exceeds the 8 MiB budget.")
                metadata = {k.lower(): v for k, v in response.headers.items()}
                # Do not retain cookies, credential material, or arbitrary response headers.
                safe = {k: metadata[k] for k in ("x-ratelimit-remaining", "x-ratelimit-reset",
                        "x-oauth-scopes", "github-authentication-token-expiration", "x-github-sso") if k in metadata}
                if "x-github-sso" in safe:
                    safe["x-github-sso"] = safe["x-github-sso"].split(";", 1)[0]
                self.access.append({"path": path, "status": response.status, "headers": safe})
                return json.loads(body), metadata
        except urllib.error.HTTPError as error:
            error.close()
            reasons = {401: "authentication failed or expired", 403: "permission, SSO, or rate limit failure",
                       404: "unavailable or unauthorized; deletion is unknown", 409: "empty repository or conflict",
                       429: "rate limited", 301: "repository redirected; verify its new identity",
                       302: "repository redirected; verify its new identity"}
            raise ProbeError(f"GitHub HTTP {error.code}: {reasons.get(error.code, 'request failed')}") from None
        except urllib.error.URLError:
            raise ProbeError("GitHub network request failed; access and deletion state are unknown.") from None


def paged(reader: GitHubReader, path: str, max_pages: int = 10) -> tuple[list, dict]:
    values = []
    for page in range(1, max_pages + 1):
        separator = "&" if "?" in path else "?"
        response, headers = reader.get(f"{path}{separator}per_page=100&page={page}")
        if not isinstance(response, list):
            raise ProbeError("Unexpected GitHub list response.")
        values.extend(response)
        if not re.search(r'rel="next"', headers.get("link", "")):
            return values, {"pages": page, "complete": True, "count": len(values)}
    return values, {"pages": max_pages, "complete": False, "count": len(values),
                    "omission": "Page budget reached; count is a lower bound."}


def probe(reader: GitHubReader, repository: str, branches: list[str], documents: list[str]) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ProbeError("Repository must be owner/name.")
    prefix = f"/repos/{repository}"
    repo, _ = reader.get(prefix)
    all_branches, branch_pages = paged(reader, prefix + "/branches")
    selected = list(dict.fromkeys(branches or [repo["default_branch"]]))
    inventory = []
    omissions = []
    sample_sha = None
    for branch in selected:
        # Pin the branch head before walking history, so a new push cannot move pages.
        head, _ = reader.get(prefix + "/branches/" + urllib.parse.quote(branch, safe=""))
        sha = head["commit"]["sha"]
        commits, pagination = paged(reader, prefix + "/commits?sha=" + urllib.parse.quote(sha, safe=""))
        inventory.append({"branch": branch, "head_sha": sha, "pagination": pagination,
                          "oldest_returned_commit": commits[-1]["sha"] if commits else None,
                          "oldest_returned_date": commits[-1]["commit"]["committer"]["date"] if commits else None})
        if sample_sha is None and commits:
            sample_sha = commits[0]["sha"]
    if sample_sha is None:
        raise ProbeError("No sample commit available; empty history is not an access failure.")
    commit, headers = reader.get(prefix + f"/commits/{sample_sha}?per_page=100&page=1")
    files = []
    for file in commit.get("files", []):
        row = {k: file.get(k) for k in ("filename", "status", "previous_filename", "additions", "deletions", "changes")}
        if file.get("patch") is None:
            row["patch"] = None
            omissions.append(f"Patch unavailable for {file['filename']}; binary/large/missing are not distinguished.")
        else:
            row["patch"] = preview(file["patch"], omissions)
        files.append(row)
    if re.search(r'rel="next"', headers.get("link", "")):
        omissions.append("Sample commit files cover page 1 only; more file pages exist.")
    document_samples = []
    for path in documents:
        if path.startswith("/") or ".." in path.split("/") or not path:
            raise ProbeError("Document paths must be repository-relative without parent traversal.")
        try:
            obj, _ = reader.get(prefix + "/contents/" + urllib.parse.quote(path, safe="/") + "?ref=" + sample_sha)
        except ProbeError as error:
            document_samples.append({"path": path, "state": "unavailable/unknown", "reason": str(error)})
            continue
        if not isinstance(obj, dict):
            document_samples.append({"path": path, "state": "omitted: expected a file, received a directory"})
            omissions.append(f"Document {path} is not a file.")
            continue
        row = {"path": path, "commit_sha": sample_sha, "blob_sha": obj.get("sha"), "size": obj.get("size")}
        if obj.get("type") != "file" or obj.get("encoding") != "base64" or obj.get("size", 0) > MAX_DOCUMENT_BYTES:
            row["state"] = "omitted: non-file, unsupported encoding, or size over 1 MiB"
            omissions.append(f"Document {path} omitted by the preview budget.")
        else:
            try:
                content = base64.b64decode(obj["content"], validate=False)
                if len(content) > MAX_DOCUMENT_BYTES:
                    raise ValueError("oversized content")
                row.update(state="available", text=preview(content.decode("utf-8"), omissions))
            except (UnicodeDecodeError, ValueError):
                row["state"] = "omitted: invalid or non-UTF-8 content"
        document_samples.append(row)
    return {"provider": "github", "parser_version": "github-rest-v1", "api_version": API_VERSION,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "repository": {"id": repo["id"], "name": repo["full_name"], "visibility": repo.get("visibility"),
                           "default_branch": repo["default_branch"], "owner_type": repo["owner"]["type"],
                           "git_size_kib": repo.get("size"), "permissions": repo.get("permissions", "not exposed")},
            "auth": {"method": "environment token" if reader.token else "anonymous public read",
                     "minimum_permission": "Contents: read; metadata read",
                     "least_privilege_verified": not bool(reader.token),
                     "token_expiry": "not applicable" if not reader.token else "see response headers; unknown if absent",
                     "organization_authorization": "not applicable" if repo["owner"]["type"] == "User" else "not inferred from successful repository access"},
            "branch_inventory": {"names": [b["name"] for b in all_branches], **branch_pages},
            "history_inventory": inventory,
            "sample": {"sha": commit["sha"], "url": commit["html_url"],
                       "message": preview(commit["commit"]["message"], omissions),
                       "author": commit["commit"]["author"], "committer": commit["commit"]["committer"],
                       "parents": [p["sha"] for p in commit["parents"]], "stats": commit.get("stats"),
                       "files": files, "documents_at_commit": document_samples},
            "access_checks": reader.access,
            "omissions": sorted(set(omissions + [
                "Only selected reachable branch history is inventoried; deleted refs and inaccessible objects are unknown.",
                "Preview checks one commit, not every historical diff/document. PRs/issues are deferred to Phase 2.4.",
                "GitHub commit file API caps history at 3,000 changed files per commit; missing patches remain gaps.",
            ])), "external_ai": "disabled; no AI requests"}

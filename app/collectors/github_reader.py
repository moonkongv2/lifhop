"""Bounded repository GETs with resumable private response caching."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from app.acquisition.common import ProbeError
from app.acquisition.github import API_VERSION, NoRedirect
from app.collectors.bundle import bytes_json, digest, private_write, read_json


class Paused(ProbeError):
    def __init__(self, code, retry_at=0):
        self.code, self.retry_at = code, retry_at
        super().__init__(code)


class RepositoryReader:
    def __init__(self, directory, config, token=None):
        self.directory, self.config, self.token = directory, config, token
        self.authenticated = bool(token)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.requests = 0
        self.deadline = time.monotonic() + config.run_seconds
        self.retry_at = 0
        if self.directory.is_symlink() or any(parent.is_symlink() for parent in self.directory.parents):
            raise ProbeError("Symlink cache directories are not allowed")
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.directory.chmod(0o700)

    def get(self, path):
        base = f"/repos/{self.config.repository}"
        endpoint = urllib.parse.urlsplit(path)
        if (endpoint.path != base and not endpoint.path.startswith(base + "/")) or any(ord(c) < 32 for c in path) or endpoint.fragment:
            raise ProbeError("Repository endpoint outside selected scope")
        if time.monotonic() >= self.deadline:
            raise Paused("RUN_LIMIT")
        cache = self.directory / (digest(path) + ".json")
        if cache.exists():
            saved = read_json(cache, 9 * 1024 * 1024)
            return saved["body"], saved["headers"]
        if time.time() < self.retry_at:
            raise Paused("RATE_LIMIT", self.retry_at)
        if self.requests >= self.config.max_requests or time.monotonic() >= self.deadline:
            raise Paused("RUN_LIMIT")
        if sum(p.stat().st_size for p in self.directory.iterdir()) > self.config.bundle_bytes:
            raise Paused("SOURCE_LIMIT")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "lifhop-github-backfill"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request("https://api.github.com" + path, headers=headers, method="GET")
        for attempt in range(3):
            if self.requests >= self.config.max_requests or time.monotonic() >= self.deadline:
                raise Paused("RUN_LIMIT")
            self.requests += 1
            try:
                with self.opener.open(request, timeout=20) as response:
                    raw = response.read(8 * 1024 * 1024 + 1)
                    safe = {k.lower(): v for k, v in response.headers.items() if k.lower() in
                        {"link", "x-ratelimit-remaining", "x-ratelimit-reset", "retry-after"}}
                if len(raw) > 8 * 1024 * 1024:
                    raise Paused("SOURCE_LIMIT")
                body = json.loads(raw)
                saved = {"body": body, "headers": safe}
                items_size = sum(p.stat().st_size for p in self.directory.parent.glob("item-*.json"))
                if items_size + sum(p.stat().st_size for p in self.directory.iterdir()) + len(bytes_json(saved)) > self.config.bundle_bytes:
                    raise Paused("SOURCE_LIMIT")
                private_write(cache, saved)
                if safe.get("x-ratelimit-remaining") == "0":
                    self.retry_at = float(safe.get("x-ratelimit-reset", time.time()+60))
                return body, safe
            except urllib.error.HTTPError as error:
                status, info = error.code, error.headers
                error.close()
                if status in {403, 429} and (status == 429 or info.get("Retry-After") or info.get("X-RateLimit-Remaining") == "0"):
                    delay = info.get("Retry-After", "60")
                    retry = time.time() + (int(delay) if delay.isdigit() else 60)
                    if info.get("X-RateLimit-Remaining") == "0":
                        retry = max(retry, float(info.get("X-RateLimit-Reset", retry)))
                    raise Paused("RATE_LIMIT", retry) from None
                if status in {401, 403, 404, 409, 301, 302, 307, 308}:
                    code = {401:"AUTH_FAILED",403:"ACCESS_DENIED",404:"REF_UNAVAILABLE",409:"CONFLICT"}.get(status,"REPOSITORY_REDIRECT")
                    if status == 403 and info.get("X-GitHub-SSO", "").startswith("required"):
                        code = "SSO_REQUIRED"
                    raise Paused(code) from None
                if status < 500 or attempt == 2:
                    raise Paused("READ_FAILED") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise Paused("TIMEOUT") from None
            except (ValueError, TypeError):
                raise Paused("FORMAT_UNSUPPORTED") from None
            time.sleep(2 ** attempt)

    def next_page(self, headers, expected_path):
        import re
        match = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("link", ""))
        if not match:
            return None
        url = urllib.parse.urlsplit(match[1])
        base = urllib.parse.urlsplit(expected_path)
        query = urllib.parse.parse_qs(url.query)
        original = urllib.parse.parse_qs(base.query)
        # GitHub canonicalizes Link paths to the numeric repository endpoint.
        prefix = f"/repos/{self.config.repository}"
        numeric = f"/repositories/{self.config.repository_id}" + base.path[len(prefix):]
        if url.scheme != "https" or url.netloc != "api.github.com" or url.path not in {base.path,numeric} or url.fragment or {k:v for k,v in query.items() if k != "page"} != {k:v for k,v in original.items() if k != "page"}:
            raise Paused("SOURCE_CONFLICT")
        try:
            if len(query["page"]) != 1:
                raise ValueError("Repeated page")
            page = int(query["page"][0])
        except (KeyError, ValueError):
            raise Paused("SOURCE_CONFLICT") from None
        if page < 1:
            raise Paused("SOURCE_CONFLICT")
        return page

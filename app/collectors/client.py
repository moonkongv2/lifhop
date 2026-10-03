import fcntl
import getpass
import json
import http.client
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from app.acquisition.common import ProbeError
from app.collectors.bundle import bytes_json, digest, private_write, read_json


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class APIError(ProbeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Collector API failed ({status}); checkpoint retained")


class CollectorAPI:
    def __init__(self, url: str):
        parsed = urllib.parse.urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.rstrip("/"):
            raise ProbeError("API URL must be an origin without credentials, query or path")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
            raise ProbeError("Use HTTPS or loopback HTTP for the collector API")
        self.origin = url.rstrip("/")
        self.token = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path: str, data=None, *, form=False):
        raw = urllib.parse.urlencode(data).encode() if form else bytes_json(data) if data is not None else None
        headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        for attempt in range(3):
            try:
                request = urllib.request.Request(self.origin + path, data=raw, headers=headers)
                with self.opener.open(request, timeout=20) as response:
                    value = response.read(2 * 1024 * 1024 + 1)
                if len(value) > 2 * 1024 * 1024:
                    raise ProbeError("Collector API response exceeds budget")
                return json.loads(value)
            except urllib.error.HTTPError as error:
                if error.code not in {429, 503} or attempt == 2:
                    raise APIError(error.code) from None
                retry = error.headers.get("Retry-After", "")
                wait = min(30, int(retry)) if retry.isdigit() else 2 ** attempt
            except (urllib.error.URLError, OSError, http.client.HTTPException):
                if attempt == 2:
                    raise APIError("network") from None
                wait = 2 ** attempt
            time.sleep(wait)

    def login(self, email: str, password: str):
        self.token = self.request("/auth/login", {"username": email, "password": password}, form=True)["access_token"]
        return self.request("/auth/me")["id"]


@contextmanager
def bundle_lock(directory: Path):
    path = directory / ".apply.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProbeError("This preview is already being applied") from None
        yield
    finally:
        os.close(fd)


def apply_bundle(directory, cfg, url, email, *, api=None, password=None):
    from app.collectors.codex import validate_bundle
    from app.schemas.collection_run import CollectorItem, RunCreate
    with bundle_lock(directory):
        manifest = validate_bundle(directory, cfg)
        api = api or CollectorAPI(url)
        owner_id = api.login(email, password if password is not None else getpass.getpass("Local lifhop password: "))
        binding = dict(api_origin=api.origin, owner_id=owner_id, scope=manifest["scope"],
            manifest_digest=manifest["manifest_digest"], parser_version=manifest["parser_version"],
            filter_version=manifest["filter_version"])
        checkpoint_path = directory / "checkpoint.json"
        if checkpoint_path.exists():
            checkpoint = read_json(checkpoint_path, 32 * 1024 * 1024)
            if checkpoint.get("binding") != binding:
                raise ProbeError("Checkpoint belongs to another owner/API/device/preview")
        else:
            checkpoint = dict(binding=binding, acknowledged=[])
        create = {key: manifest[key] for key in ("client_run_uuid", "provider", "scope", "manifest_digest",
            "parser_version", "filter_version", "expected_items", "coverage")}
        RunCreate.model_validate(create)
        run = api.request("/collection-runs", create)
        acknowledged = set(checkpoint["acknowledged"])
        for entry in manifest["items"]:
            identity = entry["external_id"]
            status = api.request(f"/collection-runs/{run['id']}/preflight?" + urllib.parse.urlencode({"external_id": identity}))
            code = status["error_code"] or entry["error_code"]
            # Recheck policy even for locally acknowledged records; never resend blocked bodies.
            saved = status.get("receipt")
            if identity in acknowledged and saved and saved["payload_digest"] == entry["payload_digest"]:
                continue
            if not code:
                data = read_json(directory / entry["file"], cfg.turn_bytes)
                if digest(data) != entry["payload_digest"]:
                    raise ProbeError("Preview changed during apply")
                try:
                    CollectorItem.model_validate(data)
                except ValueError:
                    code = "INVALID_ITEM"
            if code:
                result = api.request(f"/collection-runs/{run['id']}/outcomes", {
                    "external_id": identity, "payload_digest": entry["payload_digest"], "error_code": code})
            else:
                try:
                    result = api.request(f"/collection-runs/{run['id']}/items", data)
                except APIError as error:
                    if error.status != 422:
                        raise
                    result = api.request(f"/collection-runs/{run['id']}/outcomes", {
                        "external_id": identity, "payload_digest": entry["payload_digest"], "error_code": "INVALID_ITEM"})
            if result["external_id"] != identity or result["payload_digest"] != entry["payload_digest"]:
                raise ProbeError("Collector ACK does not match preview")
            acknowledged.add(identity)
            checkpoint["acknowledged"] = sorted(acknowledged)
            private_write(checkpoint_path, checkpoint, replace=True)
        return api.request(f"/collection-runs/{run['id']}/finish", {})

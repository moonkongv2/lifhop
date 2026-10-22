from fastapi import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings


class ImportUploadLimit:
    """Limit multipart input before it can fill the temporary spool directory."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        protected_write = scope["method"] == "POST" or (scope["method"] == "PATCH" and scope["path"].startswith('/codex-subscriptions'))
        if not protected_write or not scope["path"].startswith(("/imports/", "/collection-runs", "/collector/", "/codex-subscriptions", "/answer-conversations")):
            await self.app(scope, receive, send)
            return
        file_limit = settings.import_max_zip_bytes if scope["path"].rstrip("/") == "/imports/chatgpt" else settings.import_max_upload_bytes
        limit = 2 * 1024 * 1024 if scope["path"].startswith(("/collection-runs", "/collector/", "/codex-subscriptions")) else file_limit + 64 * 1024
        if scope["path"].startswith("/answer-conversations"):
            limit = 64 * 1024
        size = 0

        async def limited_receive():
            nonlocal size
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    raise HTTPException(413, "Upload request exceeds the configured size limit")
            return message

        await self.app(scope, limited_receive, send)

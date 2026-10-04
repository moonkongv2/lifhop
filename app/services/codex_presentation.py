from pydantic import ValidationError
from app.importers.canonical import DevSessionPayload
from app.importers.normalizer import dev_session_content


def session_ref(provider: str | None, scope: str, payload: dict | None):
    thread = (payload or {}).get("thread_id")
    if provider == "codex" and isinstance(thread, str) and 0 < len(thread) <= 1024:
        return {"source_scope": scope, "thread_id": thread}
    return None


def dev_payload(provider: str | None, payload: dict | None) -> DevSessionPayload | None:
    if provider != "codex" or not payload or payload.get("kind") != "dev_session":
        return None
    try:
        return DevSessionPayload.model_validate(payload)
    except ValidationError:
        return None


def primary_content(provider: str | None, payload: dict | None, content: str | None) -> str | None:
    parsed = dev_payload(provider, payload)
    if parsed is None:
        return None
    # Preserve legacy normalization exactly when no phase metadata was captured.
    return dev_session_content(parsed, include_work=False) if parsed.message_phases else content

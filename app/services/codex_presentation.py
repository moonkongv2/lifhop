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


def conversation_content(payload: DevSessionPayload) -> str:
    """Render recorded questions/answers separately from searchable evidence."""
    indices = [ref.index for ref in payload.order if ref.kind == "message"] if payload.order else range(len(payload.messages))
    messages = [payload.messages[index] for index in indices]
    return "\n\n".join(f"{message.role}: {message.content}" for message in messages
        if message.role in {"user", "assistant"} and not (
            message.role == "assistant" and payload.message_phases.get(message.message_id) == "commentary"))

"""Exact answer text and an allowlist of descriptive current-source metadata."""

CONTEXT_VERSION = "answer-source-context-v1"


def current_excerpt(parent, *, reference_id=None, text=None):
    # Use the same representation for recommendation byte accounting and dispatch.
    # Never serialize the full source payload (authors, patches, commands, etc.).
    ref = parent.repository_ref
    item = dict(id=parent.id if reference_id is None else reference_id,
        text=parent.text if text is None else text, title=parent.title,
        source=parent.source, source_kind=ref.kind if ref else parent.source)
    if ref:
        item.update(repository=ref.repository, path=ref.path)
    return item

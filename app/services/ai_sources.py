"""Shared source-type gate; exact event ranges are verified again at egress."""
from sqlalchemy import and_, or_, select
from app.models.entry import Entry, EntryType
from app.models.history import EntryVersion

TEXT_TYPES = [EntryType.NOTE, EntryType.DOCUMENT, EntryType.CONVERSATION]
EVENT_KINDS = ["github_commit", "github_pull_request", "github_issue",
    "github_issue_comment", "github_review", "github_review_comment"]


def allowed_type(version=None):
    # Some callers select Entries without joining their versions. Correlate only
    # Entry, so an outer historical-version join cannot change the current gate.
    kind = (select(EntryVersion.payload["kind"].astext)
        .where(EntryVersion.id == Entry.current_version_id, EntryVersion.entry_id == Entry.id)
        .correlate(Entry).scalar_subquery()) if version is None else version.payload["kind"].astext
    entry_type = Entry.type if version is None else version.entry_type
    return or_(entry_type.in_(TEXT_TYPES), and_(entry_type == EntryType.PROJECT_EVENT,
        or_(and_(Entry.provider == "codex", kind == "dev_session"),
            and_(Entry.provider == "github", kind.in_(EVENT_KINDS)))))

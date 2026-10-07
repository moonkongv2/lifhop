import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.entry import EntrySource, EntryType
from app.services.entry_search import date_boundary

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Query = Annotated[str, Field(min_length=1, max_length=256)]


class EvaluationError(Exception):
    """Public error codes never include source bodies or credentials."""


def canonical_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Filters(StrictModel):
    source: EntrySource | None = None
    source_state: Literal["available", "deleted", "unavailable", "unknown"] | None = None
    entry_type: EntryType | None = None
    date_field: Literal["created_at", "event_at"] = "created_at"
    date_from: date | None = None
    date_to: date | None = None
    include_work_commentary: bool = False

    @model_validator(mode="after")
    def dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("DATE_RANGE")
        try:
            if self.date_from:
                date_boundary(self.date_from)
            if self.date_to:
                date_boundary(self.date_to + timedelta(days=1))
        except (ValueError, OverflowError):
            raise ValueError("DATE_RANGE") from None
        return self


class Anchor(StrictModel):
    entry_id: int = Field(gt=0, strict=True)
    version_id: int = Field(gt=0, strict=True)
    content_hash: Hash
    provider: str | None = Field(default=None, max_length=50)
    source_scope: str = Field(max_length=255)
    external_id: str | None = Field(default=None, max_length=255)
    field: Literal["title", "content"] = "content"
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    passage_sha256: Hash
    selection: Literal["current", "historical"] = "current"

    @model_validator(mode="after")
    def span(self):
        if not 0 < self.end - self.start <= 8000:
            raise ValueError("PASSAGE_RANGE")
        return self


class EvidenceGroup(StrictModel):
    id: Identifier
    anchors: list[Anchor] = Field(default_factory=list, max_length=20)


class Claim(StrictModel):
    id: Identifier
    statement: str = Field(min_length=1, max_length=2000)
    required_group_ids: list[Identifier] = Field(min_length=1, max_length=20)


class Case(StrictModel):
    id: Identifier
    question: str = Field(default="", max_length=256)
    language: Literal["ko", "en", "other"] = "ko"
    tags: list[Identifier] = Field(default_factory=list, max_length=16)
    status: Literal["draft", "reviewed"] = "draft"
    expected_outcome: Literal["supported", "insufficient_evidence", "coverage_gap", "policy_excluded"] = "supported"
    keyword_queries: list[Query] = Field(default_factory=list, max_length=3)
    filters: Filters = Field(default_factory=Filters)
    claims: list[Claim] = Field(default_factory=list, max_length=20)
    evidence_groups: list[EvidenceGroup] = Field(default_factory=list, max_length=20)
    review_scope: str = Field(default="", max_length=4000)
    review_notes: str = Field(default="", max_length=4000)
    reviewed_by: int | None = Field(default=None, gt=0)
    reviewed_at: datetime | None = None

    @field_validator("keyword_queries")
    @classmethod
    def nonblank_queries(cls, values):
        if any(not query.strip() for query in values):
            raise ValueError("EMPTY_QUERY")
        return values

    @model_validator(mode="after")
    def references(self):
        groups = [group.id for group in self.evidence_groups]
        claims = [claim.id for claim in self.claims]
        if len(set(groups)) != len(groups) or len(set(claims)) != len(claims):
            raise ValueError("DUPLICATE_ID")
        if any(group not in groups for claim in self.claims for group in claim.required_group_ids):
            raise ValueError("UNKNOWN_GROUP")
        if sum(len(group.anchors) for group in self.evidence_groups) > 20:
            raise ValueError("ANCHOR_LIMIT")
        if self.status == "reviewed":
            if any(claim.statement.startswith("[Candidate]") for claim in self.claims):
                raise ValueError("CANDIDATE_CLAIM_REQUIRES_EDIT")
            if not self.question.strip() or not self.reviewed_by or not self.reviewed_at or self.reviewed_at.utcoffset() is None:
                raise ValueError("REVIEW_REQUIRED")
            if self.expected_outcome in {"supported", "policy_excluded"}:
                if not self.claims or not self.required_groups() or any(not group.anchors for group in self.required_groups()):
                    raise ValueError("EVIDENCE_REQUIRED")
            elif not self.review_scope.strip() or not self.review_notes.strip():
                raise ValueError("NEGATIVE_REVIEW_REQUIRED")
        elif self.reviewed_by is not None or self.reviewed_at is not None:
            raise ValueError("DRAFT_REVIEW_METADATA")
        return self

    def required_groups(self) -> list[EvidenceGroup]:
        ids = {group for claim in self.claims for group in claim.required_group_ids}
        return [group for group in self.evidence_groups if group.id in ids]


class Dataset(StrictModel):
    schema_version: Literal["lifhop-evaluation-v1"] = "lifhop-evaluation-v1"
    material_kind: Literal["private_real", "synthetic"] = "private_real"
    set_id: Identifier
    revision: int = Field(ge=1, le=1000)
    parent_digest: Hash | None = None
    owner_id: int = Field(gt=0)
    owner_email: str = Field(min_length=1, max_length=255)
    database_fingerprint: Hash
    created_at: datetime
    cases: list[Case] = Field(min_length=1, max_length=100)
    digest: Hash

    @model_validator(mode="after")
    def integrity(self):
        if self.created_at.utcoffset() is None:
            raise ValueError("AWARE_TIME_REQUIRED")
        if (self.revision == 1) != (self.parent_digest is None):
            raise ValueError("REVISION_CHAIN")
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("DUPLICATE_CASE")
        if any(case.status == "reviewed" and case.reviewed_by != self.owner_id for case in self.cases):
            raise ValueError("REVIEW_OWNER")
        if self.digest != digest(self.model_dump(mode="json", exclude={"digest"})):
            raise ValueError("DATASET_DIGEST")
        return self


def dataset_from(value: dict) -> Dataset:
    value = dict(value)
    value.pop("digest", None)
    # Normalize defaults and dates before hashing the complete schema.
    value["cases"] = [Case.model_validate(case).model_dump(mode="json") for case in value["cases"]]
    value.setdefault("schema_version", "lifhop-evaluation-v1")
    value.setdefault("material_kind", "private_real")
    value.setdefault("parent_digest", None)
    if isinstance(value.get("created_at"), datetime):
        value["created_at"] = value["created_at"].isoformat().replace("+00:00", "Z")
    value["digest"] = digest(value)
    return Dataset.model_validate(value)

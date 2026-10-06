"""Typed, source-identified GitHub discussion evidence."""
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ObjectId = Annotated[int, Field(gt=0, lt=10**20)]
SHA = Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
DISCUSSION_OBJECTS = ("pull_request", "issue", "issue_comment", "review", "review_comment")


class GitHubDiscussionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: ObjectId
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=255)
    object_id: ObjectId
    number: ObjectId
    author: str | None = Field(default=None, max_length=255)
    author_id: ObjectId | None = None
    body: str
    body_state: Literal["available", "empty", "unavailable"]
    created_at: datetime | None = None
    updated_at: datetime | None = None
    omissions: list[str] = Field(default_factory=list, max_length=100)
    filter_version: str = Field(min_length=1, max_length=100)

    @field_validator("created_at", "updated_at", check_fields=False)
    @classmethod
    def aware(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError("Source timestamps require an offset")
        return value

    @field_validator("repository")
    @classmethod
    def repository_name(cls, value):
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("Invalid repository name")
        return value

    @model_validator(mode="after")
    def body_status(self):
        if self.body_state != "available" and self.body:
            raise ValueError("Empty/unavailable bodies must not contain text")
        return self


class GitHubDiscussionRoot(GitHubDiscussionPayload):
    title: str = Field(min_length=1, max_length=255)
    state: Literal["open", "closed"]
    state_reason: str | None = Field(default=None, max_length=100)
    labels: list[str] = Field(default_factory=list, max_length=100)
    closed_at: datetime | None = None

    @field_validator("closed_at")
    @classmethod
    def aware_closed(cls, value):
        return cls.aware(value)


class GitHubPullRequestPayload(GitHubDiscussionRoot):
    kind: Literal["github_pull_request"] = "github_pull_request"
    merged: bool
    draft: bool
    merged_at: datetime | None = None
    base_sha: SHA | None = None
    head_sha: SHA | None = None
    merge_sha: SHA | None = None
    commits: list[SHA] = Field(default_factory=list, max_length=250)
    commits_complete: bool

    @field_validator("merged_at")
    @classmethod
    def aware_merged(cls, value):
        return cls.aware(value)


class GitHubIssuePayload(GitHubDiscussionRoot):
    kind: Literal["github_issue"] = "github_issue"


class GitHubDiscussionChild(GitHubDiscussionPayload):
    parent_kind: Literal["pull_request", "issue"]
    parent_id: ObjectId
    parent_external_id: str = Field(max_length=255)

    @model_validator(mode="after")
    def parent_identity(self):
        if self.parent_external_id != f"repo:{self.repository_id}:{self.parent_kind}:{self.parent_id}":
            raise ValueError("Parent identity does not match repository/kind/ID")
        if self.kind != "github_issue_comment" and self.parent_kind != "pull_request":
            raise ValueError("Reviews require a pull request parent")
        return self


class GitHubIssueCommentPayload(GitHubDiscussionChild):
    kind: Literal["github_issue_comment"] = "github_issue_comment"


class GitHubReviewPayload(GitHubDiscussionChild):
    kind: Literal["github_review"] = "github_review"
    state: Literal["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"]
    submitted_at: datetime | None = None
    commit_id: SHA | None = None

    @field_validator("submitted_at")
    @classmethod
    def aware_submitted(cls, value):
        return cls.aware(value)

    @model_validator(mode="after")
    def no_invented_edit_clock(self):
        if self.updated_at is not None:
            raise ValueError("Review REST evidence has no verified edit clock")
        return self


class GitHubReviewCommentPayload(GitHubDiscussionChild):
    kind: Literal["github_review_comment"] = "github_review_comment"
    review_id: ObjectId | None = None
    in_reply_to_id: ObjectId | None = None
    path: str | None = Field(default=None, max_length=4096)
    diff_hunk: str | None = None
    line: int | None = Field(default=None, ge=1)
    original_line: int | None = Field(default=None, ge=1)
    start_line: int | None = Field(default=None, ge=1)
    original_start_line: int | None = Field(default=None, ge=1)
    side: Literal["LEFT", "RIGHT"] | None = None
    start_side: Literal["LEFT", "RIGHT"] | None = None
    commit_id: SHA | None = None
    original_commit_id: SHA | None = None

    @field_validator("path")
    @classmethod
    def relative_path(cls, value):
        if value is not None and (value.startswith("/") or any(p in {"", ".", ".."} for p in value.split("/"))
                or any(ord(c) < 32 for c in value)):
            raise ValueError("Invalid repository-relative path")
        return value


GitHubDiscussionEvidence = (GitHubPullRequestPayload | GitHubIssuePayload | GitHubIssueCommentPayload
    | GitHubReviewPayload | GitHubReviewCommentPayload)


def discussion_external_id(payload):
    return f"repo:{payload.repository_id}:{payload.kind.removeprefix('github_')}:{payload.object_id}"


def discussion_parent(payload):
    if isinstance(payload, GitHubDiscussionChild):
        return payload.parent_kind, payload.parent_id
    return payload.kind.removeprefix("github_"), payload.object_id


def discussion_locator(payload):
    kind, _ = discussion_parent(payload)
    url = f"https://github.com/{payload.repository}/{'pull' if kind == 'pull_request' else 'issues'}/{payload.number}"
    anchor = {"github_issue_comment": "issuecomment", "github_review": "pullrequestreview",
        "github_review_comment": "discussion_r"}.get(payload.kind)
    return url + (f"#{anchor}{'' if anchor == 'discussion_r' else '-'}{payload.object_id}" if anchor else "")

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas.passage import PassageResponse


class AnswerRequest(BaseModel):
    q: str = Field(min_length=1, max_length=256)
    request_id: str = Field(pattern="^[a-f0-9]{32}$")
    embedding_ids: list[int] | None = Field(default=None, min_length=1, max_length=5)
    passage_ids: list[int] | None = Field(default=None, min_length=1, max_length=5)
    confirm_external_ai: bool = False
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def one_source(self):
        if (self.embedding_ids is None) == (self.passage_ids is None):
            raise ValueError("Select either Semantic slices or Passages, not both")
        return self


class AnswerCitation(BaseModel):
    kind: Literal["embedding", "passage"]
    source_id: int
    passage: PassageResponse


class AnswerResponse(BaseModel):
    status: Literal["supported", "insufficient"]
    answer: str
    citations: list[AnswerCitation]
    policy_revision: int
    model_config = ConfigDict(extra="forbid")


class AnswerStatus(BaseModel):
    enabled: bool
    policy_revision: int
    selected_limit: int = 5
    max_input_characters: int = 10000
    output_limit_tokens: int = 512


class RecommendationRequest(BaseModel):
    q: str = Field(min_length=1, max_length=256)
    embedding_ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(min_length=1, max_length=20)
    policy_revision: int = Field(strict=True, ge=0)
    model_config = ConfigDict(extra="forbid")

    @field_validator("q")
    @classmethod
    def nonblank_question(cls, value):
        if not value.strip():
            raise ValueError("Question must not be blank")
        return value

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.embedding_ids)) != len(self.embedding_ids):
            raise ValueError("Duplicate candidate IDs")
        return self


class RecommendationOmission(BaseModel):
    embedding_id: int
    rank: int
    reason: Literal["duplicate_parent", "count_limit", "byte_limit"]


class RecommendationResponse(BaseModel):
    passages: list[PassageResponse]
    omissions: list[RecommendationOmission]
    policy_revision: int
    request_bytes: int

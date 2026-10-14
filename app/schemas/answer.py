from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
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

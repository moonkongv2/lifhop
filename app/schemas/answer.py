from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.passage import PassageResponse


class AnswerRequest(BaseModel):
    q: str = Field(min_length=1, max_length=256)
    request_id: str = Field(pattern="^[a-f0-9]{32}$")
    embedding_ids: list[int] = Field(min_length=1, max_length=5)
    confirm_external_ai: bool = False
    model_config = ConfigDict(extra="forbid")


class AnswerCitation(BaseModel):
    embedding_id: int
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
    max_input_characters: int = 3000
    output_limit_tokens: int = 512

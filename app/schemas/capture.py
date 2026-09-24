from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CaptureMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    message_id: str | None = None


class CaptureDiagnostics(BaseModel):
    message_count: int = Field(ge=1)
    reached_top: bool
    reached_bottom: bool
    first_message_role: str | None = None


class ChatGPTCaptureRequest(BaseModel):
    ok: Literal[True]
    provider: Literal["chatgpt"]

    external_id: str = Field(
        min_length=1,
        max_length=255,
    )
    title: str = Field(
        min_length=1,
        max_length=255,
    )
    source_url: str | None = None

    messages: list[CaptureMessage] = Field(
        min_length=1,
    )

    diagnostics: CaptureDiagnostics

    @model_validator(mode="after")
    def validate_capture(self):
        if not (
            self.diagnostics.reached_top
            and self.diagnostics.reached_bottom
        ):
            raise ValueError(
                "Conversation capture is incomplete"
            )

        if (
            self.diagnostics.message_count
            != len(self.messages)
        ):
            raise ValueError(
                "Captured message count mismatch"
            )

        if self.messages[0].role != "user":
            raise ValueError(
                "First captured message must be from user"
            )

        return self

"""Pydantic schemas for the /agent/chat endpoint.

Design notes (06-CONTEXT.md / 06-RESEARCH.md):
  - ChatRequest.message: min_length=1, max_length=2000 (Pydantic validation → 422 on violation).
  - ChatRequest.history: up to 20 prior {role, content} messages (D-73 rolling window).
  - ChatResponse.answer: a single prose string synthesized by the agent loop.
"""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    """A single message in the conversation history."""

    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=2000)


class ChatRequest(BaseModel):
    """Request body for POST /agent/chat.

    Validation:
      - message: non-empty, max 2000 chars (prevents runaway prompts / T-6-03).
      - history: at most 20 prior messages (D-73 rolling window, T-6-04 context cap).
      - history must start with a "user" turn and alternate roles — rejects
        crafted assistant turns injected to manipulate Claude's behavior.
    """

    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_history_alternation(self) -> "ChatRequest":
        if not self.history:
            return self
        if self.history[0].role != "user":
            raise ValueError("history must begin with a user message")
        for i in range(1, len(self.history)):
            if self.history[i].role == self.history[i - 1].role:
                raise ValueError(
                    f"history roles must alternate; consecutive {self.history[i].role!r} at index {i}"
                )
        return self


class ChatResponse(BaseModel):
    """Response body for POST /agent/chat."""

    answer: str

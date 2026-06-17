"""Pydantic schemas for the /agent/chat endpoint.

Design notes (06-CONTEXT.md / 06-RESEARCH.md):
  - ChatRequest.message: min_length=1, max_length=2000 (Pydantic validation → 422 on violation).
  - ChatRequest.history: up to 20 prior {role, content} messages (D-73 rolling window).
  - ChatResponse.answer: a single prose string synthesized by the agent loop.
"""
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in the conversation history."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Request body for POST /agent/chat.

    Validation:
      - message: non-empty, max 2000 chars (prevents runaway prompts / T-6-03).
      - history: at most 20 prior messages (D-73 rolling window, T-6-04 context cap).
    """

    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    """Response body for POST /agent/chat."""

    answer: str

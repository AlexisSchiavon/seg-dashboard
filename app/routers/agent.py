"""Agent router — POST /agent/chat endpoint for the NL query interface.

All endpoints require a valid JWT cookie (router-level dependency, T-6-05).
Business logic lives in app/services/agent.py — this router only wires
HTTP concerns (request parsing, response serialization, error mapping).

Security notes:
  - Router-level dependencies=[Depends(get_current_user)] protects ALL endpoints.
    Returns 401 for unauthenticated requests (T-6-05, verified by test_chat_requires_auth).
  - chat() endpoint is declared `def` (NOT `async def`) — the Anthropic SDK
    client.messages.create() is a synchronous blocking call; FastAPI runs `def`
    endpoints in a threadpool (Pitfall 3 from RESEARCH.md).
  - ValueError from agent_service (unknown tool, unexpected Claude response) → HTTP 502.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.schemas.agent import ChatRequest, ChatResponse
from app.services import agent as agent_service

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(get_current_user)],  # router-level auth — T-6-05
)


@router.post("/chat", response_model=ChatResponse)
def chat(  # MUST be `def` NOT `async def` — Anthropic SDK is blocking (Pitfall 3)
    body: ChatRequest,
    db: Session = Depends(get_db),
):
    """Run the agentic tool-use loop and return a prose answer.

    Accepts an optional conversation history (D-73 multi-turn) alongside the
    new user message. History is client-supplied and never persisted server-side.

    Errors:
      - 401 if no valid JWT cookie (router-level dependency)
      - 422 if message is empty or > 2000 chars, or history > 20 messages (Pydantic)
      - 502 if the Anthropic API call fails or returns an unexpected structure
    """
    try:
        answer = agent_service.chat(
            db,
            body.message,
            [m.model_dump() for m in body.history],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el agente",
        ) from exc
    return ChatResponse(answer=answer)

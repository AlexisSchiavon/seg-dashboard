"""Tests for the embedded natural-language agent (Phase 6, Plan 01).

Test Map:
  TestChatEndpoint:
    - test_chat_returns_answer: authed POST /agent/chat returns 200 with {answer} key.
    - test_chat_requires_auth: unauthenticated POST returns 401.
    - test_chat_empty_message: {"message": ""} returns 422.
    - test_chat_message_too_long: message > 2000 chars returns 422.

  TestToolExecutor:
    - test_execute_tool_dispatches_all: _execute_tool dispatches each of 11 tool names
      to the correct service function; unknown name raises ValueError.
    - test_tool_definitions_complete: TOOL_DEFINITIONS has exactly 11 entries, each with
      name, description, and input_schema with type "object".

  TestAgentLoop:
    - test_max_tool_calls: loop performs at most 5 tool executions then returns.
    - test_loop_returns_text_on_end_turn: when stop_reason == "end_turn", loop returns
      text without executing any tools.
"""

import pytest
from unittest.mock import MagicMock, call


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_anthropic_agent(monkeypatch):
    """Mock Anthropic client for agent tests.

    Monkeypatches app.services.agent.anthropic.Anthropic so no real API
    calls are made. Default response: stop_reason="end_turn" with a text block.

    Configure mock_client.messages.create.side_effect or .return_value in each
    test to simulate different scenarios (tool_use, multiple rounds, etc.).
    """

    def make_text_response(text="Respuesta de prueba."):
        resp = MagicMock()
        resp.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = text
        resp.content = [text_block]
        return resp

    def make_tool_use_response(tool_name="global_kpis", tool_id="toolu_test_01", tool_input=None):
        """Build a response with stop_reason='tool_use' and one tool_use block."""
        resp = MagicMock()
        resp.stop_reason = "tool_use"
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = tool_id
        tool_block.name = tool_name
        tool_block.input = tool_input if tool_input is not None else {}
        resp.content = [tool_block]
        return resp

    mock_client = MagicMock()
    mock_client.messages.create.return_value = make_text_response()

    # Attach helpers so tests can call mock_client.make_text_response(...)
    mock_client.make_text_response = make_text_response
    mock_client.make_tool_use_response = make_tool_use_response

    monkeypatch.setattr(
        "app.services.agent.anthropic.Anthropic",
        lambda **kwargs: mock_client,
    )
    return mock_client


# ---------------------------------------------------------------------------
# TestChatEndpoint — integration tests via FastAPI TestClient
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    """Integration tests for POST /agent/chat."""

    def test_chat_returns_answer(self, auth_client, seed_talent_products, mock_anthropic_agent):
        """Authenticated POST /agent/chat with a valid message returns 200 and {answer}."""
        response = auth_client.post(
            "/agent/chat",
            json={"message": "¿Cuál es el revenue global?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_chat_requires_auth(self, client):
        """Unauthenticated POST /agent/chat returns 401."""
        response = client.post(
            "/agent/chat",
            json={"message": "¿Cuál es el revenue global?"},
        )
        assert response.status_code == 401

    def test_chat_empty_message(self, auth_client):
        """POST /agent/chat with an empty message returns 422 (Pydantic validation)."""
        response = auth_client.post(
            "/agent/chat",
            json={"message": ""},
        )
        assert response.status_code == 422

    def test_chat_message_too_long(self, auth_client):
        """POST /agent/chat with message > 2000 chars returns 422."""
        long_message = "a" * 2001
        response = auth_client.post(
            "/agent/chat",
            json={"message": long_message},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# TestToolExecutor — unit tests for _execute_tool dispatcher
# ---------------------------------------------------------------------------


class TestToolExecutor:
    """Unit tests for _execute_tool and TOOL_DEFINITIONS."""

    def test_execute_tool_dispatches_all(self, db_session, seed_talent_products, monkeypatch):
        """_execute_tool dispatches each of the 11 tool names to the right service function.

        Each service function is replaced by a sentinel MagicMock; after calling
        _execute_tool with the corresponding name, we assert the sentinel was called.
        Unknown tool name raises ValueError.
        """
        from app.services import agent as agent_module

        talent_id = seed_talent_products["talent_a"].id

        # Build sentinel mocks for all 11 service functions
        sentinels = {
            "global_kpis": MagicMock(return_value={"total": 0}),
            "talent_ranking": MagicMock(return_value=[]),
            "talent_detail": MagicMock(return_value={}),
            "funnel_overview": MagicMock(return_value={}),
            "talent_funnel": MagicMock(return_value=[]),
            "recent_activity": MagicMock(return_value=[]),
            "income_projection": MagicMock(return_value=[]),
            "payment_calendar": MagicMock(return_value=[]),
            "deals_for_talent": MagicMock(return_value=[]),
            "leads_summary": MagicMock(return_value={}),
            "leads_by_talent": MagicMock(return_value=[]),
        }

        # Patch each service function used by _execute_tool
        monkeypatch.setattr(agent_module.kpi_service, "global_kpis", sentinels["global_kpis"])
        monkeypatch.setattr(agent_module.kpi_service, "talent_ranking", sentinels["talent_ranking"])
        monkeypatch.setattr(agent_module.kpi_service, "talent_detail", sentinels["talent_detail"])
        monkeypatch.setattr(agent_module.funnel_service, "funnel_overview", sentinels["funnel_overview"])
        monkeypatch.setattr(agent_module.funnel_service, "talent_funnel", sentinels["talent_funnel"])
        monkeypatch.setattr(agent_module.funnel_service, "recent_activity", sentinels["recent_activity"])
        monkeypatch.setattr(agent_module.trello_service, "income_projection", sentinels["income_projection"])
        monkeypatch.setattr(agent_module.trello_service, "payment_calendar", sentinels["payment_calendar"])
        monkeypatch.setattr(agent_module.trello_service, "deals_for_talent", sentinels["deals_for_talent"])
        monkeypatch.setattr(agent_module.leads_service, "leads_summary", sentinels["leads_summary"])
        monkeypatch.setattr(agent_module.leads_service, "leads_by_talent", sentinels["leads_by_talent"])

        # No-param tools
        agent_module._execute_tool("global_kpis", {}, db_session)
        sentinels["global_kpis"].assert_called_once_with(db_session)

        agent_module._execute_tool("talent_ranking", {}, db_session)
        sentinels["talent_ranking"].assert_called_once_with(db_session)

        agent_module._execute_tool("funnel_overview", {}, db_session)
        sentinels["funnel_overview"].assert_called_once_with(db_session)

        agent_module._execute_tool("leads_summary", {}, db_session)
        sentinels["leads_summary"].assert_called_once_with(db_session)

        agent_module._execute_tool("leads_by_talent", {}, db_session)
        sentinels["leads_by_talent"].assert_called_once_with(db_session)

        # recent_activity — optional limit param
        agent_module._execute_tool("recent_activity", {}, db_session)
        sentinels["recent_activity"].assert_called_once_with(db_session, 20)

        # Per-talent tools
        agent_module._execute_tool("talent_detail", {"talent_id": talent_id}, db_session)
        sentinels["talent_detail"].assert_called_once_with(db_session, talent_id)

        agent_module._execute_tool("talent_funnel", {"talent_id": talent_id}, db_session)
        sentinels["talent_funnel"].assert_called_once_with(db_session, talent_id)

        agent_module._execute_tool("income_projection", {"talent_id": talent_id}, db_session)
        sentinels["income_projection"].assert_called_once_with(db_session, talent_id)

        agent_module._execute_tool("payment_calendar", {"talent_id": talent_id}, db_session)
        sentinels["payment_calendar"].assert_called_once_with(db_session, talent_id)

        agent_module._execute_tool("deals_for_talent", {"talent_id": talent_id}, db_session)
        sentinels["deals_for_talent"].assert_called_once_with(db_session, talent_id)

        # Unknown tool name raises ValueError
        with pytest.raises(ValueError, match="Unknown tool"):
            agent_module._execute_tool("nonexistent_tool", {}, db_session)

    def test_tool_definitions_complete(self):
        """TOOL_DEFINITIONS has exactly 11 entries; every entry has the required fields."""
        from app.services.agent import TOOL_DEFINITIONS

        assert len(TOOL_DEFINITIONS) == 11, (
            f"Expected 11 tool definitions, got {len(TOOL_DEFINITIONS)}"
        )

        for tool in TOOL_DEFINITIONS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool.get('name')!r} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool.get('name')!r} missing 'input_schema'"
            schema = tool["input_schema"]
            assert schema.get("type") == "object", (
                f"Tool {tool.get('name')!r} input_schema.type must be 'object', got {schema.get('type')!r}"
            )


# ---------------------------------------------------------------------------
# TestAgentLoop — unit tests for _run_agent_loop behavior
# ---------------------------------------------------------------------------


class TestAgentLoop:
    """Unit tests for the tool-use agentic loop in app/services/agent.py."""

    def test_loop_returns_text_on_end_turn(self, db_session, seed_talent_products, mock_anthropic_agent):
        """When first response stop_reason == 'end_turn', loop returns text without tools."""
        from app.services import agent as agent_module

        # Default fixture already returns an end_turn response
        result = agent_module._run_agent_loop(
            db=db_session,
            message="¿Cuál es el revenue global?",
            history=[],
        )

        assert isinstance(result, str)
        assert result == "Respuesta de prueba."
        # messages.create was called exactly once (no tool round-trips)
        mock_anthropic_agent.messages.create.assert_called_once()

    def test_max_tool_calls(self, db_session, seed_talent_products, mock_anthropic_agent, monkeypatch):
        """Loop performs at most 5 tool executions, then returns.

        Arrange: mock Anthropic always returns tool_use so the loop would run forever
        without the MAX_TOOL_CALLS ceiling.
        Assert: _execute_tool is called at most 5 times; loop still returns a string.
        """
        from app.services import agent as agent_module

        # Track _execute_tool calls
        tool_call_count = 0

        def counting_execute_tool(name, tool_input, db):
            nonlocal tool_call_count
            tool_call_count += 1
            return {"result": f"tool_{tool_call_count}"}

        monkeypatch.setattr(agent_module, "_execute_tool", counting_execute_tool)

        # Anthropic: always returns a tool_use response (would loop forever without ceiling)
        # Except the final synthesis call after ceiling — return text there
        call_count = {"n": 0}

        def side_effect_fn(*args, **kwargs):
            call_count["n"] += 1
            # After MAX_TOOL_CALLS tool executions, the loop calls create() one more time
            # for synthesis. Return text for any call that is not tool_use.
            if call_count["n"] <= agent_module.MAX_TOOL_CALLS + 1:
                return mock_anthropic_agent.make_tool_use_response(
                    tool_name="global_kpis", tool_id=f"toolu_{call_count['n']:02d}"
                )
            # Final synthesis call
            return mock_anthropic_agent.make_text_response("Respuesta parcial disponible.")

        mock_anthropic_agent.messages.create.side_effect = side_effect_fn

        result = agent_module._run_agent_loop(
            db=db_session,
            message="Pregunta que dispara muchas herramientas",
            history=[],
        )

        assert isinstance(result, str)
        # Tool execution count must not exceed MAX_TOOL_CALLS (5)
        assert tool_call_count <= agent_module.MAX_TOOL_CALLS, (
            f"Expected at most {agent_module.MAX_TOOL_CALLS} tool calls, got {tool_call_count}"
        )

"""
Phase 4 — LLM Provider abstraction.

Two implementations:

  MockLLMProvider
    • Satisfies langchain-core's Runnable interface.
    • When wrapped via with_structured_output(schema), intercepts the schema and
      returns a deterministic, perfectly valid JSON string that matches it —
      eliminating the "mock returns a plain string, parser crashes" trap.
    • Thread-safe, no I/O, instant.

  OpenAILLMProvider (stub — enabled when OPENAI_API_KEY is set)
    • Wraps langchain_openai.ChatOpenAI.
    • Automatically uses with_structured_output when a schema is requested.

The factory function get_llm() is the single entry point. Always use
  llm = get_llm()
  structured = llm.with_structured_output(MySchema)
  result = await structured.ainvoke(prompt)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Deterministic mock values keyed by schema name ──────────────────────────

_MOCK_RESPONSES: dict[str, dict[str, Any]] = {
    "TicketClassification": {
        "category": "infrastructure",
        "priority": "high",
        "severity": "s2",
        "confidence": 0.87,
        "reasoning": "Ticket describes a service-level infrastructure issue with elevated priority signals.",
    },
    "TicketDiagnosis": {
        "root_cause": "Resource exhaustion due to a misconfigured connection pool or memory leak.",
        "affected_components": ["primary-db", "api-gateway", "load-balancer"],
        "impact_summary": "Users are experiencing intermittent 500 errors and elevated latency.",
        "evidence": [
            "OOMKilled events detected in pod logs",
            "Connection pool at 100% utilisation",
            "Runbook: Redis Cache Operations confirms cache miss cascade pattern",
        ],
        "confidence": 0.82,
    },
    "TicketRecommendation": {
        "action": "Restart affected service pods and apply connection-pool tuning.",
        "steps": [
            "1. Drain traffic from affected nodes via load balancer.",
            "2. Scale down and restart the affected deployment.",
            "3. Apply environment variable patch: MAX_POOL_SIZE=20.",
            "4. Monitor error rate for 10 minutes before re-routing traffic.",
        ],
        "estimated_resolution_time": "30-45 minutes",
        "risk_level": "medium",
        "requires_approval": False,
        "runbook_references": ["Redis Cache Operations Runbook", "Incident Response Playbook"],
        "confidence": 0.79,
    },
    "TicketActionProposal": {
        "proposed_action": "restart_production_service",
        "action_arguments": {"service_name": "postgres-primary", "force": True},
        "confidence": 0.95,
    },
}


class _StructuredOutputRunnable(Runnable):
    """
    Wraps MockLLMProvider.with_structured_output() result.

    On ainvoke(), returns a deterministic Pydantic model instance that exactly
    matches the requested schema — satisfying the structured output contract
    without any LLM API calls.
    """

    def __init__(self, schema: type) -> None:
        self._schema = schema

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:  # noqa: A002
        schema_name = self._schema.__name__
        mock_data = _MOCK_RESPONSES.get(schema_name, {})
        logger.debug("MockLLMProvider.with_structured_output() → %s (mock)", schema_name)
        return self._schema(**mock_data)

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:  # noqa: A002
        # Simulate negligible async latency without blocking the event loop
        return self.invoke(input, config, **kwargs)


class MockLLMProvider(BaseChatModel):
    """
    A LangChain-compatible mock LLM that satisfies all Phase 4 contracts:

    • with_structured_output(schema) → returns deterministic Pydantic instances.
    • ainvoke(messages) → returns a plain AIMessage with safe text for
      unstructured nodes (e.g. summarisation).
    • Zero latency, no I/O, fully deterministic.
    """

    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        content = (
            "Mock LLM response — no API call made. "
            "Use with_structured_output() for typed nodes."
        )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, **kwargs)

    def with_structured_output(  # type: ignore[override]
        self,
        schema: type,
        **kwargs: Any,
    ) -> _StructuredOutputRunnable:
        """
        Override with_structured_output to return a mock runnable that
        produces deterministic, schema-valid Pydantic instances.

        This prevents the "mock returns plain text, parser crashes" trap.
        """
        return _StructuredOutputRunnable(schema)


# ─── OpenAI provider (production) ────────────────────────────────────────────

class OpenAILLMProvider:
    """
    Thin wrapper around langchain_openai.ChatOpenAI.

    Raises ImportError at construction time if langchain-openai is not installed,
    so the error is clear and immediate rather than buried in a trace.
    """

    def __init__(self) -> None:
        try:
            from langchain_openai import ChatOpenAI  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "langchain-openai is not installed. "
                "Add it to requirements.txt or set LLM_PROVIDER=mock."
            ) from exc

        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not configured. "
                "Set it in .env or use LLM_PROVIDER=mock for development."
            )

        self._llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,           # Deterministic outputs for agent nodes
            max_retries=2,
        )
        logger.info("OpenAILLMProvider initialised (model=%s)", settings.LLM_MODEL)

    def with_structured_output(self, schema: type, **kwargs: Any) -> Runnable:
        return self._llm.with_structured_output(schema, **kwargs)

    async def ainvoke(self, messages: list, **kwargs: Any) -> AIMessage:
        return await self._llm.ainvoke(messages, **kwargs)


# ─── Factory ─────────────────────────────────────────────────────────────────

def get_llm() -> MockLLMProvider | OpenAILLMProvider:
    """
    Return the configured LLM provider.

    Controlled by settings.LLM_PROVIDER:
      "mock"   → MockLLMProvider (deterministic, no API key needed — default)
      "openai" → OpenAILLMProvider (requires OPENAI_API_KEY)
    """
    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        logger.info("Using OpenAILLMProvider")
        return OpenAILLMProvider()
    if provider != "mock":
        logger.warning(
            "Unknown LLM_PROVIDER '%s'; falling back to MockLLMProvider.", provider
        )
    logger.info("Using MockLLMProvider (deterministic, no API call)")
    return MockLLMProvider()

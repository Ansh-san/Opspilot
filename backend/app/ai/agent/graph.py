"""
Phase 4 — LangGraph Agent Graph with fully implemented nodes.

Architecture
------------
START → classify_ticket → retrieve_knowledge → generate_diagnosis
      → generate_recommendation → finalize → END

All traps addressed:
  1. Structured output: every LLM call uses llm.with_structured_output(Schema).
     A retry-once wrapper catches parse failures and re-invokes with RETRY_SUFFIX.
  2. Mock LLM: MockLLMProvider.with_structured_output() returns deterministic
     Pydantic instances — never plain text.
  3. Prompt injection: all user/retrieved content is wrapped in XML delimiters
     (<ticket>, <context>) with an explicit system SECURITY INSTRUCTION.
  4. Async: every node is async def; graph is invoked with ainvoke() only.
  5. List reducers: retrieved_documents and errors use _append so nodes append
     instead of overwrite.

Important: the graph is a singleton compiled once at module load. Pass the
async db session via config["configurable"]["db"] when calling ainvoke().
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.prompts import (
    CLASSIFY_PROMPT,
    DIAGNOSE_PROMPT,
    RECOMMEND_PROMPT,
    PROPOSE_ACTION_PROMPT,
    RETRY_SUFFIX,
)
from app.ai.agent.retriever import AgentRetriever
from app.ai.agent.schemas import (
    TicketClassification,
    TicketDiagnosis,
    TicketRecommendation,
    TicketActionProposal,
)
from app.ai.tools.registry import tool_registry
from app.ai.agent.state import AgentState
from app.ai.evaluation.registry import eval_registry
from app.ai.llm import get_llm

logger = logging.getLogger(__name__)


# ─── Context formatter (prompt-injection safe) ───────────────────────────────

def _format_context(chunks: list[dict[str, Any]]) -> str:
    """
    Render retrieved knowledge chunks as a plain text block.

    The outer <context> delimiter and SECURITY INSTRUCTION are added by the
    prompt template — this function only formats the inner content.
    """
    if not chunks:
        return "(No relevant knowledge base documents found.)"

    parts = []
    for i, c in enumerate(chunks, 1):
        title = c.get("document_title", "Unknown")
        page = c.get("page") or "?"
        score = c.get("similarity_score") or 0.0
        content = c.get("content", "")
        parts.append(
            f"[{i}] Document: {title} | Page: {page} | Score: {score:.3f}\n{content}"
        )
    return "\n\n".join(parts)


# ─── Retry-aware LLM invocation ──────────────────────────────────────────────

async def _invoke_structured(
    chain: Any,
    variables: dict[str, Any],
    schema_name: str,
) -> Any:
    """
    Invoke a structured-output chain (prompt | llm.with_structured_output(Schema)).

    On parse failure, retry once with RETRY_SUFFIX appended to the last human
    message.  Raises on second failure so the node can catch and record the error.
    """
    try:
        return await chain.ainvoke(variables)
    except Exception as first_err:  # noqa: BLE001
        logger.warning(
            "Structured parse failed for %s: %s — retrying with strict prompt.",
            schema_name, first_err,
        )
        # Append RETRY_SUFFIX to the last human message by modifying the variables
        retry_vars = {**variables}
        # Inject the retry instruction into a special variable that prompts can use
        # (simpler than rewriting the ChatPromptTemplate at runtime)
        last_key = list(retry_vars.keys())[-1]
        retry_vars[last_key] = str(retry_vars[last_key]) + RETRY_SUFFIX
        try:
            return await chain.ainvoke(retry_vars)
        except Exception as second_err:  # noqa: BLE001
            logger.error(
                "Structured parse failed again for %s: %s", schema_name, second_err
            )
            raise


# ─── Node: classify_ticket ────────────────────────────────────────────────────

async def classify_ticket(state: AgentState, config: dict) -> dict[str, Any]:
    """
    Node 1: Classify category, priority, severity, confidence.

    Uses CLASSIFY_PROMPT (XML delimited) + with_structured_output(TicketClassification).
    Gracefully catches errors and appends to state["errors"].
    """
    logger.info("▶ classify_ticket | ticket=%s", state["ticket_id"])
    try:
        llm = get_llm()
        chain = CLASSIFY_PROMPT | llm.with_structured_output(TicketClassification)
        ticket = state["ticket_data"]

        classification: TicketClassification = await _invoke_structured(
            chain,
            {
                "title": ticket.get("title", ""),
                "description": ticket.get("description", ""),
                "affected_service": ticket.get("affected_service", "unknown"),
            },
            "TicketClassification",
        )
        logger.info(
            "✓ classify_ticket → category=%s priority=%s severity=%s confidence=%.2f",
            classification.category,
            classification.priority,
            classification.severity,
            classification.confidence,
        )
        return {"classification": classification, "errors": []}
    except Exception as exc:  # noqa: BLE001
        logger.exception("✗ classify_ticket failed: %s", exc)
        return {"classification": None, "errors": [f"Classification failed: {exc}"]}


# ─── Node: retrieve_knowledge ─────────────────────────────────────────────────

async def retrieve_knowledge(state: AgentState, config: dict) -> dict[str, Any]:
    """
    Node 2: Semantic search against the Phase 3 knowledge base.

    Uses the ticket title + description as the query.  Results are appended to
    retrieved_documents via the _append reducer (not overwritten).

    Requires config["configurable"]["db"] (AsyncSession) to be passed in
    via graph.ainvoke(..., config={"configurable": {"db": db}}).
    """
    logger.info("▶ retrieve_knowledge | ticket=%s", state["ticket_id"])
    try:
        db: AsyncSession = config["configurable"]["db"]
        retriever = AgentRetriever(db)

        ticket = state["ticket_data"]
        query = f"{ticket.get('title', '')} {ticket.get('description', '')}".strip()

        chunks = await retriever.retrieve(
            query=query,
            org_id=state["org_id"],
            top_k=5,
        )
        logger.info("✓ retrieve_knowledge → %d chunks retrieved", len(chunks))
        return {"retrieved_documents": chunks, "errors": []}
    except Exception as exc:  # noqa: BLE001
        logger.exception("✗ retrieve_knowledge failed: %s", exc)
        return {"retrieved_documents": [], "errors": [f"Knowledge retrieval failed: {exc}"]}


# ─── Node: generate_diagnosis ─────────────────────────────────────────────────

async def generate_diagnosis(state: AgentState, config: dict) -> dict[str, Any]:
    """
    Node 3: Root-cause analysis using ticket data + retrieved knowledge context.

    Uses DIAGNOSE_PROMPT with XML delimiters + with_structured_output(TicketDiagnosis).
    The retrieved context is formatted as plain text inside <context> tags in the
    prompt template — never executed as instructions.
    """
    logger.info("▶ generate_diagnosis | ticket=%s", state["ticket_id"])
    try:
        llm = get_llm()
        chain = DIAGNOSE_PROMPT | llm.with_structured_output(TicketDiagnosis)
        ticket = state["ticket_data"]
        classification = state.get("classification")
        context_text = _format_context(state.get("retrieved_documents") or [])

        diagnosis: TicketDiagnosis = await _invoke_structured(
            chain,
            {
                "title": ticket.get("title", ""),
                "description": ticket.get("description", ""),
                "category": classification.category if classification else "unknown",
                "priority": classification.priority if classification else "unknown",
                "severity": classification.severity if classification else "unknown",
                "affected_service": ticket.get("affected_service", "unknown"),
                "context": context_text,
            },
            "TicketDiagnosis",
        )
        logger.info(
            "✓ generate_diagnosis → root_cause=%r confidence=%.2f",
            diagnosis.root_cause[:60],
            diagnosis.confidence,
        )
        return {"diagnosis": diagnosis, "errors": []}
    except Exception as exc:  # noqa: BLE001
        logger.exception("✗ generate_diagnosis failed: %s", exc)
        return {"diagnosis": None, "errors": [f"Diagnosis failed: {exc}"]}


# ─── Node: generate_recommendation ───────────────────────────────────────────

async def generate_recommendation(state: AgentState, config: dict) -> dict[str, Any]:
    """
    Node 4: Concrete remediation plan based on diagnosis + knowledge context.

    Uses RECOMMEND_PROMPT with XML delimiters + with_structured_output(TicketRecommendation).
    Sets requires_approval=True automatically if risk_level is 'high' or 'blocked'.
    """
    logger.info("▶ generate_recommendation | ticket=%s", state["ticket_id"])
    try:
        llm = get_llm()
        chain = RECOMMEND_PROMPT | llm.with_structured_output(TicketRecommendation)
        ticket = state["ticket_data"]
        diagnosis = state.get("diagnosis")
        context_text = _format_context(state.get("retrieved_documents") or [])

        recommendation: TicketRecommendation = await _invoke_structured(
            chain,
            {
                "title": ticket.get("title", ""),
                "affected_service": ticket.get("affected_service", "unknown"),
                "root_cause": diagnosis.root_cause if diagnosis else "unknown",
                "affected_components": (
                    ", ".join(diagnosis.affected_components) if diagnosis else "unknown"
                ),
                "impact_summary": diagnosis.impact_summary if diagnosis else "unknown",
                "context": context_text,
            },
            "TicketRecommendation",
        )
        # Enforce approval gate: high/blocked risk always requires approval
        if recommendation.risk_level in ("high", "blocked"):
            object.__setattr__(recommendation, "requires_approval", True)  # Pydantic v2 safe

        logger.info(
            "✓ generate_recommendation → risk=%s requires_approval=%s confidence=%.2f",
            recommendation.risk_level,
            recommendation.requires_approval,
            recommendation.confidence,
        )
        return {"recommendation": recommendation, "errors": []}
    except Exception as exc:  # noqa: BLE001
        logger.exception("✗ generate_recommendation failed: %s", exc)
        return {"recommendation": None, "errors": [f"Recommendation failed: {exc}"]}


# ─── Node: propose_action ────────────────────────────────────────────────────

async def propose_action(state: AgentState, config: dict) -> dict[str, Any]:
    """
    Node 5: Propose a specific tool execution based on the recommendation.
    
    Uses PROPOSE_ACTION_PROMPT with XML delimiters + with_structured_output(TicketActionProposal).
    Dynamically feeds the registered tools from ToolRegistry.
    """
    logger.info("▶ propose_action | ticket=%s", state["ticket_id"])
    try:
        llm = get_llm()
        chain = PROPOSE_ACTION_PROMPT | llm.with_structured_output(TicketActionProposal)
        ticket = state["ticket_data"]
        diagnosis = state.get("diagnosis")
        recommendation = state.get("recommendation")
        
        # Build available tools string
        available_tools = "\n".join([
            f"- {t.name}: {t.description}" for t in tool_registry.list_tools()
        ])

        proposal: TicketActionProposal = await _invoke_structured(
            chain,
            {
                "title": ticket.get("title", ""),
                "affected_service": ticket.get("affected_service", "unknown"),
                "root_cause": diagnosis.root_cause if diagnosis else "unknown",
                "action": recommendation.action if recommendation else "unknown",
                "steps": (", ".join(recommendation.steps) if recommendation else "unknown"),
                "available_tools": available_tools,
            },
            "TicketActionProposal",
        )
        logger.info(
            "✓ propose_action → action=%s confidence=%.2f",
            proposal.proposed_action,
            proposal.confidence,
        )
        # Convert Pydantic object to dict for the state (or pass directly depending on how state handles it, 
        # but the state dict expects dict[str, Any] for action_proposal)
        return {"action_proposal": proposal.model_dump(), "errors": []}
    except Exception as exc:  # noqa: BLE001
        logger.exception("✗ propose_action failed: %s", exc)
        return {"action_proposal": None, "errors": [f"Action proposal failed: {exc}"]}



# ─── Node: finalize ───────────────────────────────────────────────────────────

async def finalize(state: AgentState, config: dict) -> dict[str, Any]:
    """
    Node 5: Synthesise final confidence, risk_level, and token_usage.

    Risk level computation:
      - If recommendation.risk_level exists, use it.
      - Otherwise escalate based on classification severity:
          s1/critical → high, s2/high → medium, else → low.
      - Any errors in state → escalate to 'high' as a safety measure.

    Does NOT call the LLM.
    """
    logger.info("▶ finalize | ticket=%s", state["ticket_id"])

    classification = state.get("classification")
    diagnosis = state.get("diagnosis")
    recommendation = state.get("recommendation")
    errors = state.get("errors") or []

    # Weighted average of per-node confidences
    confidences = [
        c for c in [
            classification.confidence if classification else None,
            diagnosis.confidence if diagnosis else None,
            recommendation.confidence if recommendation else None,
        ]
        if c is not None
    ]
    overall_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    # Determine risk level
    if recommendation:
        risk_level = recommendation.risk_level
    elif classification:
        risk_level = {
            "critical": "high",
            "high": "medium",
            "medium": "medium",
            "low": "low",
        }.get(classification.priority, "medium")
    else:
        risk_level = "high"

    # Safety escalation: any node failures → high risk
    if errors:
        logger.warning("finalize: %d errors present, escalating risk to high.", len(errors))
        risk_level = "high"

    logger.info(
        "✓ finalize → confidence=%.4f risk=%s errors=%d",
        overall_confidence, risk_level, len(errors),
    )
    
    # Run evaluation
    # Since we need to mimic the ai_run_data payload, we construct it from the state
    eval_payload = {
        "ticket_data": state.get("ticket_data"),
        "retrieved_documents": state.get("retrieved_documents") or [],
        "classification": classification.model_dump() if classification else None,
        "diagnosis": diagnosis.model_dump() if diagnosis else None,
        "recommendation": recommendation.model_dump() if recommendation else None,
        "action_proposal": state.get("action_proposal"),
        "confidence": overall_confidence,
        "risk_level": risk_level,
        "policy_result": {}, # Finalize node doesn't know policy result, but ToolPolicyEvaluator relies on it. 
                             # Wait! We shouldn't evaluate tool policy here, since it requires the agent_service's routing!
    }
    
    # ToolPolicy and HumanOverride require data not available until after the run and approval lifecycle.
    # Therefore, the registry running in `finalize` will just yield EXPECTED/NOT_EVALUATED for those,
    # which is fine. They can be re-evaluated later via the endpoint.
    evaluation_results = eval_registry.run_all(eval_payload)

    return {
        "confidence": overall_confidence,
        "risk_level": risk_level,
        "token_usage": {"input_tokens": 0, "output_tokens": 0},  # populated for real LLMs
        "errors": [],
        "evaluation_results": evaluation_results,
    }


# ─── Graph assembly ───────────────────────────────────────────────────────────

def _build_graph() -> Any:
    builder = StateGraph(AgentState)

    builder.add_node("classify_ticket", classify_ticket)
    builder.add_node("retrieve_knowledge", retrieve_knowledge)
    builder.add_node("generate_diagnosis", generate_diagnosis)
    builder.add_node("generate_recommendation", generate_recommendation)
    builder.add_node("propose_action", propose_action)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "classify_ticket")
    builder.add_edge("classify_ticket", "retrieve_knowledge")
    builder.add_edge("retrieve_knowledge", "generate_diagnosis")
    builder.add_edge("generate_diagnosis", "generate_recommendation")
    builder.add_edge("generate_recommendation", "propose_action")
    builder.add_edge("propose_action", "finalize")
    builder.add_edge("finalize", END)

    compiled = builder.compile()
    logger.info("LangGraph agent compiled successfully.")
    return compiled


# Singleton — compiled once at module import, reused across all requests.
agent_graph = _build_graph()

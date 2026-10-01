from typing import Any
from dataclasses import dataclass

from app.ai.policy.rules import RiskLevel, PolicyDecision, TOOL_RISK_MAPPING
from app.ai.tools.registry import tool_registry


@dataclass
class PolicyResult:
    risk_level: RiskLevel
    decision: PolicyDecision
    reason: str


class PolicyEngine:
    """
    Evaluates proposed actions (tool calls) against deterministic rules.
    """

    @staticmethod
    def evaluate(action: str, args: dict[str, Any], context: dict[str, Any]) -> PolicyResult:
        """
        Evaluate a proposed tool execution.
        Returns the assessed RiskLevel and the resulting PolicyDecision.
        """
        
        # 1. Does the tool exist?
        tool = tool_registry.get_tool(action)
        if not tool:
            return PolicyResult(
                risk_level=RiskLevel.BLOCKED,
                decision=PolicyDecision.REJECT,
                reason=f"Tool '{action}' is not registered in the system."
            )
            
        # 2. Lookup static risk mapping
        risk = TOOL_RISK_MAPPING.get(action, RiskLevel.HIGH)  # Default to HIGH for unknown but registered tools

        # 3. Determine decision based on risk level
        if risk == RiskLevel.LOW:
            decision = PolicyDecision.AUTO_EXECUTE
            reason = f"Action '{action}' is assessed as LOW risk and is safe for auto-execution."
        elif risk in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            decision = PolicyDecision.REQUIRE_APPROVAL
            reason = f"Action '{action}' is assessed as {risk.value.upper()} risk and requires human approval."
        else:
            decision = PolicyDecision.REJECT
            reason = f"Action '{action}' is assessed as BLOCKED and cannot be executed."

        return PolicyResult(risk_level=risk, decision=decision, reason=reason)

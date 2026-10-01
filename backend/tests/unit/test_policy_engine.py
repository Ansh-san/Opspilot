from app.ai.policy.engine import PolicyEngine
from app.ai.policy.rules import PolicyDecision, RiskLevel

# Note: The tool_registry is a global singleton that automatically registers
# the simulated tools upon import of app.ai.tools.simulated (which might not happen
# automatically in tests unless explicitly imported).
import app.ai.tools.simulated  # noqa


def test_evaluate_low_risk_auto_execute():
    result = PolicyEngine.evaluate("get_service_health", {"service_name": "api"}, {})
    assert result.risk_level == RiskLevel.LOW
    assert result.decision == PolicyDecision.AUTO_EXECUTE


def test_evaluate_medium_risk_requires_approval():
    result = PolicyEngine.evaluate("restart_test_service", {"service_name": "api"}, {})
    assert result.risk_level == RiskLevel.MEDIUM
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL


def test_evaluate_high_risk_requires_approval():
    result = PolicyEngine.evaluate("restart_production_service", {"service_name": "api"}, {})
    assert result.risk_level == RiskLevel.HIGH
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL


def test_evaluate_unknown_tool_rejected():
    result = PolicyEngine.evaluate("some_fake_tool", {}, {})
    assert result.risk_level == RiskLevel.BLOCKED
    assert result.decision == PolicyDecision.REJECT
    assert "not registered" in result.reason

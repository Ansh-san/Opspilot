from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class PolicyDecision(str, Enum):
    AUTO_EXECUTE = "auto_execute"
    REQUIRE_APPROVAL = "require_approval"
    REJECT = "reject"


# Hardcoded mapping for Phase 5
TOOL_RISK_MAPPING: dict[str, RiskLevel] = {
    # Read-only operations are generally low risk
    "get_service_health": RiskLevel.LOW,
    "get_application_logs": RiskLevel.LOW,
    
    # Test/Staging environment mutations
    "restart_test_service": RiskLevel.MEDIUM,
    
    # Production mutations
    "restart_production_service": RiskLevel.HIGH,
    
    # Destructive or highly sensitive operations
    "rollback_production_deployment": RiskLevel.HIGH,
    
    # Explicitly blocked tools (e.g., if we were to define dangerous ops)
    "drop_production_database": RiskLevel.BLOCKED,
}

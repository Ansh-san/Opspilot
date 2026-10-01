from app.ai.tools.registry import tool_registry

from .get_application_logs import GetApplicationLogsTool
from .get_service_health import GetServiceHealthTool
from .restart_production_service import RestartProductionServiceTool
from .restart_test_service import RestartTestServiceTool
from .rollback_production_deployment import RollbackProductionDeploymentTool

# Register all simulated tools immediately upon import
tool_registry.register(GetServiceHealthTool())
tool_registry.register(GetApplicationLogsTool())
tool_registry.register(RestartTestServiceTool())
tool_registry.register(RestartProductionServiceTool())
tool_registry.register(RollbackProductionDeploymentTool())

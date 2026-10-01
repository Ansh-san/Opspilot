from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.base import ToolDefinition


class GetServiceHealthSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_name: str = Field(..., description="The name of the service to check.")
    region: str = Field("us-east-1", description="The AWS region.")


class GetServiceHealthTool(ToolDefinition):
    input_schema = GetServiceHealthSchema

    def __init__(self):
        super().__init__(
            name="get_service_health",
            description="Fetch the current health status and metrics of a given service.",
            is_simulated=True,
        )

    async def execute(self, service_name: str, region: str) -> dict[str, Any]:
        # Simulated realistic JSON response
        return {
            "service": service_name,
            "region": region,
            "status": "DEGRADED",
            "active_tasks": 45,
            "cpu_utilization_pct": 89.4,
            "memory_utilization_pct": 72.1,
            "recent_errors": 12,
            "last_deployment": "2023-10-15T14:32:00Z"
        }

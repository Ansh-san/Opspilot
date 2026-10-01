from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.base import ToolDefinition


class RestartProductionServiceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_name: str = Field(..., description="The name of the production service to restart.")
    grace_period_seconds: int = Field(30, description="Grace period before killing tasks.")


class RestartProductionServiceTool(ToolDefinition):
    input_schema = RestartProductionServiceSchema

    def __init__(self):
        super().__init__(
            name="restart_production_service",
            description="Restart a critical service in the production environment.",
            is_simulated=True,
        )

    async def execute(self, service_name: str, grace_period_seconds: int) -> dict[str, Any]:
        return {
            "status": "success",
            "message": f"Successfully restarted production service {service_name} with {grace_period_seconds}s grace period.",
            "job_id": "job-prod-1234",
            "timestamp": "2023-10-15T15:10:00Z"
        }

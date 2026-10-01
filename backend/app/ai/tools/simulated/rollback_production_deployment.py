from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.base import ToolDefinition


class RollbackProductionDeploymentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_name: str = Field(..., description="The name of the service to rollback.")
    target_version: str = Field(..., description="The version tag to rollback to.")
    reason: str = Field(..., description="Reason for rolling back.")


class RollbackProductionDeploymentTool(ToolDefinition):
    input_schema = RollbackProductionDeploymentSchema

    def __init__(self):
        super().__init__(
            name="rollback_production_deployment",
            description="Rollback a production deployment to a previous known good version. Highly sensitive.",
            is_simulated=True,
        )

    async def execute(self, service_name: str, target_version: str, reason: str) -> dict[str, Any]:
        return {
            "status": "success",
            "message": f"Rolled back {service_name} to version {target_version}. Reason: {reason}",
            "job_id": "job-rollback-999",
            "timestamp": "2023-10-15T15:20:00Z"
        }

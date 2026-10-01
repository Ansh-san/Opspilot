from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.base import ToolDefinition


class RestartTestServiceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_name: str = Field(..., description="The name of the test service to restart.")
    environment: str = Field("staging", description="The test environment (staging, dev).")


class RestartTestServiceTool(ToolDefinition):
    input_schema = RestartTestServiceSchema

    def __init__(self):
        super().__init__(
            name="restart_test_service",
            description="Restart a service in a non-production (test/staging) environment.",
            is_simulated=True,
        )

    async def execute(self, service_name: str, environment: str) -> dict[str, Any]:
        return {
            "status": "success",
            "message": f"Successfully restarted {service_name} in {environment}",
            "job_id": "job-test-7890",
            "timestamp": "2023-10-15T15:05:00Z"
        }

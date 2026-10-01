from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.base import ToolDefinition


class GetApplicationLogsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_name: str = Field(..., description="The name of the service to fetch logs for.")
    lines: int = Field(50, description="Number of recent log lines to fetch.")
    level: str = Field("ERROR", description="Log level filter (INFO, WARN, ERROR, DEBUG).")


class GetApplicationLogsTool(ToolDefinition):
    input_schema = GetApplicationLogsSchema

    def __init__(self):
        super().__init__(
            name="get_application_logs",
            description="Fetch recent application logs from a given service.",
            is_simulated=True,
        )

    async def execute(self, service_name: str, lines: int, level: str) -> dict[str, Any]:
        return {
            "service": service_name,
            "level_filter": level,
            "lines_returned": min(lines, 3),
            "logs": [
                f"[2023-10-15T15:01:23Z] [{level}] Connection timeout to database pg-primary.local",
                f"[2023-10-15T15:01:25Z] [{level}] Connection timeout to database pg-primary.local",
                f"[2023-10-15T15:01:27Z] [{level}] Connection timeout to database pg-primary.local",
            ]
        }

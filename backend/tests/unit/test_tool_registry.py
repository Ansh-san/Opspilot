import pytest
from pydantic import ValidationError

from app.ai.tools.base import ToolDefinition
from app.ai.tools.registry import ToolExecutionError, ToolRegistry
from app.ai.tools.simulated.get_service_health import GetServiceHealthTool
from app.ai.tools.simulated.restart_production_service import RestartProductionServiceTool


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    r = ToolRegistry()
    r.register(GetServiceHealthTool())
    r.register(RestartProductionServiceTool())
    return r


def test_register_duplicate_tool_raises_error(registry):
    with pytest.raises(ValueError, match="is already registered"):
        registry.register(GetServiceHealthTool())


def test_get_and_list_tools(registry):
    assert len(registry.list_tools()) == 2
    tool = registry.get_tool("get_service_health")
    assert tool is not None
    assert tool.name == "get_service_health"
    assert registry.get_tool("nonexistent") is None


@pytest.mark.asyncio
async def test_execute_tool_success(registry):
    result = await registry.execute_tool(
        "get_service_health",
        {"service_name": "auth-service", "region": "eu-west-1"}
    )
    assert result["service"] == "auth-service"
    assert result["region"] == "eu-west-1"


@pytest.mark.asyncio
async def test_execute_tool_missing_required_fields(registry):
    # service_name is required for get_service_health
    with pytest.raises(ToolExecutionError, match="Invalid arguments"):
        await registry.execute_tool("get_service_health", {"region": "eu-west-1"})


@pytest.mark.asyncio
async def test_execute_tool_extra_fields_forbidden(registry):
    # The Pydantic schema has extra='forbid', so extra fields must crash it
    with pytest.raises(ToolExecutionError, match="Invalid arguments"):
        await registry.execute_tool(
            "get_service_health",
            {"service_name": "auth-service", "malicious_injection": "drop table"}
        )


@pytest.mark.asyncio
async def test_execute_unknown_tool(registry):
    with pytest.raises(ToolExecutionError, match="Unknown tool requested"):
        await registry.execute_tool("nuke_world", {})

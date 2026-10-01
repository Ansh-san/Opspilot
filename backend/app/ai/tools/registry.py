from typing import Any

from pydantic import ValidationError

from app.ai.tools.base import ToolDefinition


class ToolExecutionError(Exception):
    """Exception raised when a tool fails to execute or validate."""
    pass


class ToolRegistry:
    """
    Central registry for all AI tools.
    Strictly validates arguments against the tool's Pydantic schema before execution.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} is already registered.")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Retrieve a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    async def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool by name with the given raw dictionary arguments.
        Enforces strict Pydantic schema validation (extra='forbid') before execution.
        """
        tool = self.get_tool(name)
        if not tool:
            raise ToolExecutionError(f"Unknown tool requested: {name}")

        # Validate arguments strictly against the schema
        try:
            validated_args_model = tool.input_schema.model_validate(args)
        except ValidationError as e:
            raise ToolExecutionError(f"Invalid arguments for tool '{name}': {e.errors()}") from e

        # Convert back to dict for the kwargs
        validated_kwargs = validated_args_model.model_dump()

        try:
            return await tool.execute(**validated_kwargs)
        except Exception as e:
            raise ToolExecutionError(f"Error executing tool '{name}': {str(e)}") from e


# Global singleton registry
tool_registry = ToolRegistry()

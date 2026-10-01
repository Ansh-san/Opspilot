import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class ToolDefinition(ABC):
    """
    Base abstraction for an OpsPilot Tool.
    Every tool must define a strict Pydantic input_schema.
    """

    # Every subclass must declare its schema
    input_schema: ClassVar[type[BaseModel]]
    
    name: str
    description: str
    is_simulated: bool = False

    def __init__(self, name: str, description: str, is_simulated: bool = False):
        self.name = name
        self.description = description
        self.is_simulated = is_simulated
        
        # Enforce that subclasses defined the input_schema properly
        if not hasattr(self, "input_schema") or not issubclass(self.input_schema, BaseModel):
            raise ValueError(f"Tool {self.name} MUST define a Pydantic BaseModel as `input_schema`.")
        
        # Enforce extra='forbid' on the schema configuration
        config = self.input_schema.model_config
        if config.get("extra") != "forbid":
            raise ValueError(f"Tool {self.name} input_schema MUST have `model_config = ConfigDict(extra='forbid')`.")

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the tool with the validated arguments.
        Must return a JSON-serializable dictionary.
        """
        pass

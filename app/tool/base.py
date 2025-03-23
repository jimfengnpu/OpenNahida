from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field, SkipValidation

from app.agent.base import BaseAgent


class BaseTool(ABC, BaseModel):
    name: str
    description: str
    parameters: Optional[dict] = None
    wait: bool = True
    call_back: Optional[Callable] = None
    agent: Optional[BaseAgent] = None

    class Config:
        arbitrary_types_allowed = True

    def set_agent(self, agent):
        self.agent:BaseAgent = agent

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""

    def __str__(self):
        return f"tool:{self.name}"

    def to_param(self) -> Dict:
        """Convert tool to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def get_param_type(self, param_name) -> type:
        params = self.parameters or {}
        if not params:
            return None
        param_type = params['properties'][param_name]['type']
        if param_type == "string":
            return str
        elif param_type == "integer":
            return int


class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    output: Any = Field(default=None)
    error: Optional[str] = Field(default=None)
    system: Optional[str] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __bool__(self):
        return any(getattr(self, field) for field in self.__fields__)

    def __add__(self, other: "ToolResult"):
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            system=combine_fields(self.system, other.system),
        )

    def __str__(self):
        return f"Error: {self.error}" if self.error else self.output

    def replace(self, **kwargs):
        """Returns a new ToolResult with the given fields replaced."""
        # return self.copy(update=kwargs)
        return type(self)(**{**self.model_dump(), **kwargs})


class CLIResult(ToolResult):
    """A ToolResult that can be rendered as a CLI output."""


class ToolFailure(ToolResult):
    """A ToolResult that represents a failure."""


class AgentAwareTool:
    agent: Optional = None

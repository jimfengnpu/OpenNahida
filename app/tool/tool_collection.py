"""Collection classes for managing multiple tools."""
from typing import Any, Dict, List

from app.exceptions import ToolError
from app.tool.base import BaseTool, ToolFailure, ToolResult
from app.agent.base import BaseAgent
from app.logger import logger

class ToolCollection:
    """A collection of defined tools."""

    def __init__(self, *tools: BaseTool):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}

    def __iter__(self):
        return iter(self.tools)
    
    def set_agent(self, agent):
        self.agent:BaseAgent = agent
        for tool in self.tools:
            tool.set_agent(agent=agent)


    def to_params(self) -> List[Dict[str, Any]]:
        return [tool.to_param() for tool in self.tools]

    async def execute(
        self, *, name: str, call_id:str, tool_input: Dict[str, Any] = None
    ) -> ToolResult:
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            if not tool.wait:
                tool.call_back = lambda s: self.agent.update_memory('tool', content=s, name=name, tool_call_id=call_id)
            for k,v in tool_input.items():
                t = tool.get_param_type(k)
                if not t:
                    logger.debug(f"extra args:{k}:{v}({type(v)})")
                    continue
                if not isinstance(v, t):
                    logger.debug(f"{k}:{v}({type(v)}),get:{t}")
                    tool_input[k] = t(v)

            result = await tool(**tool_input)
            return result
        except ToolError as e:
            return ToolFailure(error=e.message)

    async def execute_all(self) -> List[ToolResult]:
        """Execute all tools in the collection sequentially."""
        results = []
        for tool in self.tools:
            try:
                result = await tool()
                results.append(result)
            except ToolError as e:
                results.append(ToolFailure(error=e.message))
        return results

    def get_tool(self, name: str) -> BaseTool:
        return self.tool_map.get(name)

    def add_tool(self, tool: BaseTool):
        self.tools += (tool,)
        self.tool_map[tool.name] = tool
        return self

    def add_tools(self, *tools: BaseTool):
        for tool in tools:
            self.add_tool(tool)
        return self

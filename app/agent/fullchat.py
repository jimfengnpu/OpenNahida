import json
from json import JSONDecodeError
from random import randint
from typing import Any, List, Literal
from datetime import datetime
from pydantic import Field

from app.agent.react import ReActAgent
from app.async_timer import AsyncTimer
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import AgentState, Message, ToolCall, ChatMessage
from app.tool import CreateChatCompletion, Terminate, ToolCollection


TOOL_CALL_REQUIRED = "Tool calls required but none provided"
TIMER_ID_AGENT_ACTIVE = "agent_active"

class FullChatAgent(ReActAgent):
    """Agent class for and handling tool/function calls/chat"""

    name: str = "full_chat"
    description: str = "an agent that can chat besides execute tool calls"

    system_prompt: str = SYSTEM_PROMPT
    extra_system_prompt: str = ""
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion(), Terminate()
    )
    tool_choices: Literal["none", "auto", "required"] = "auto"
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)

    max_steps: int = 30
    min_active_check_minutes: int = 30
    max_active_check_minutes: int = 60
    context_recent: int = 3
    context_related: int = 1
    active_check: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system_prompt += self.extra_system_prompt
        self.available_tools.set_agent(self)
        if self.active_check:
            AsyncTimer.register_event(TIMER_ID_AGENT_ACTIVE, self.check_active)
            self.start_auto_active()

    async def step(self) -> str:
        """Execute a single step: think and act."""
        should_act = await self.think()
        result = ""
        response_result = self.messages[-1].content
        if should_act:
            result = await self.act()
        if response_result:
            self.state = AgentState.FINISHED
            result += f"\n{self.name}:{response_result}"
        print(result, flush=True)
        return result

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        context_messages = self.memory.get_context_messages(self.messages[-1] if len(self.messages) >= 1 else None, self.context_recent, self.context_related)
        # Get response with tool options
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt + f"#timestamp:{str(datetime.now())}")
            context_messages += [user_msg]
        response = await self.llm.ask_tool(
            messages=context_messages,
            system_msgs=[Message.system_message(self.system_prompt)]
            if self.system_prompt
            else None,
            tools=self.available_tools.to_params(),
            tool_choice=self.tool_choices,
            response_format={"type": "json_object"},
        )
        logger.debug(response)
        if response.content:
            try:
                response_text = response.content.split("</think>")[-1]
                start = response_text.find("{")
                end = response_text.rfind("}")
                response_text = response_text[start:end + 1] if start != -1 and end != -1 else response_text
                response_josn_dict = json.loads(response_text)
                response = ChatMessage(**response_josn_dict)
            except JSONDecodeError:
                pass
        self.tool_calls = response.tool_calls

        if response.tool_calls:
            logger.debug(response.tool_calls)
            logger.info(
                f"🧰 Tools being prepared: {[call.function.name for call in response.tool_calls]}"
            )

        try:
            # Handle different tool_choices modes
            if self.tool_choices == "none":
                if response.tool_calls:
                    logger.warning(
                        f"🤔 Hmm, {self.name} tried to use tools when they weren't available!"
                    )
                if response.content:
                    await self.update_memory_message(Message.assistant_message(response.content))
                    return True
                return False

            # Create and add assistant message
            assistant_msg = (
                Message.from_tool_calls(
                    content=response.content, tool_calls=self.tool_calls
                )
                if self.tool_calls
                else Message.assistant_message(response.content)
            )
            await self.update_memory_message(assistant_msg)

            if self.tool_choices == "required" and not self.tool_calls:
                return True  # Will be handled in act()

            # For 'auto' mode, continue with content if no commands but content exists
            if self.tool_choices == "auto" and not self.tool_calls:
                return bool(response.content)

            return bool(self.tool_calls)
        except Exception as e:
            logger.error(f"🚨 Oops! The {self.name}'s thinking process hit a snag: {e}")
            self.update_memory_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}"
                )
            )
            return False

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        if not self.tool_calls:
            if self.tool_choices == "required":
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            return ""

        results = []
        for command in self.tool_calls:
            result = await self.execute_tool(command)
            logger.debug(
                f"🎯 Tool '{command.function.name}' completed its mission! Result: {result}"
            )

            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result, tool_call_id=command.id, name=command.function.name
            )
            await self.update_memory_message(tool_msg)
            results.append(result)

        return "\n".join(results)

    async def execute_tool(self, command: ToolCall) -> str:
        """Execute a single tool call with robust error handling"""
        if not command or not command.function or not command.function.name:
            return "Error: Invalid command format"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            # Parse arguments
            args = command.function.arguments.replace("\'", "\"")

            logger.info(f"🔧 Activating tool: '{name}'...")
            while not isinstance(args, dict):
                args = json.loads(args or "{}")

            # Execute the tool
            result = await self.available_tools.execute(name=name, call_id=command.id, tool_input=args)

            # Format result for display
            observation = (
                f"Cmd `{name}` executed:\n{str(result)}"
                if result
                else f"Cmd `{name}` completed with no output"
            )

            # Handle special tools like `finish`
            await self._handle_special_tool(name=name, result=result)

            return observation
        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON"
            )
            return f"Error: {error_msg}"
        except KeyboardInterrupt:
            error_msg = f"⚠️ Tool '{name}' interrupted by user"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tool execution and state changes"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            # Set agent state to finished
            logger.info(f"🏁 Special tool '{name}' has completed the task!")
            self.state = AgentState.FINISHED

    async def active_check_do(self):
        if self.state == AgentState.RUNNING:
            return
        ACTIVE_CHECK_PROMPT = """This request is automatically initiated by the system, you can respond or reply nothing, \
the response message will be regarded as an active message request, if the time is not appropriate, do not reply.
"""
        return await self.run(ACTIVE_CHECK_PROMPT, role='system')

    async def check_active(self):
        print()
        await self.active_check_do()
        print("\n>>>", end="")
        self.start_auto_active()

    def start_auto_active(self):
        interval = randint(self.min_active_check_minutes, self.max_active_check_minutes)
        logger.debug(f"System active check:{interval}minutes")
        AsyncTimer.add_event(TIMER_ID_AGENT_ACTIVE, datetime.now().timestamp() + 60*interval)

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """Check if tool name is in special tools list"""
        return name.lower() in [n.lower() for n in self.special_tool_names]

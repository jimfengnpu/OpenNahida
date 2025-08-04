from pydantic import Field

from app.agent.fullchat import FullChatAgent
from app.prompt.nahida import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import Memory
from app.tool import Terminate, ToolCollection
from app.tool.file_saver import FileSaver
from app.tool.web_search import WebSearch
from app.tool.user_notify import UserNotify

class Nahida(FullChatAgent):
    """
    A versatile general-purpose agent that uses planning to solve various tasks.

    This agent extends PlanningAgent with a comprehensive set of tools and capabilities,
    including Python execution, web browsing, file operations, and information retrieval
    to handle a wide range of user requests.
    """

    name: str = "纳西妲"
    description: str = (
        "ai agent for nahida"
    )

    memory: Memory = Field(default_factory=lambda: Memory(backend_db_file="data/db/nahida.db"))

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            WebSearch(), FileSaver(), UserNotify(), Terminate()
        )
    )

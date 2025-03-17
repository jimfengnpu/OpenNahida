from enum import Enum
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator
from pydantic_sqlite import DataBase
import numpy as np
from os import path
import json


class Role(str, Enum):
    """Message role options"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


ROLE_VALUES = tuple(role.value for role in Role)
ROLE_TYPE = Literal[ROLE_VALUES]  # type: ignore


class ToolChoice(str, Enum):
    """Tool choice options"""

    NONE = "none"
    AUTO = "auto"
    REQUIRED = "required"


TOOL_CHOICE_VALUES = tuple(choice.value for choice in ToolChoice)
TOOL_CHOICE_TYPE = Literal[TOOL_CHOICE_VALUES]  # type: ignore


class AgentState(str, Enum):
    """Agent execution states"""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class Function(BaseModel):
    name: str
    arguments: str

    @field_validator('arguments', mode="before")
    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            return v
        elif isinstance(v, dict):
            return json.dumps(v)


class ToolCall(BaseModel):
    """Represents a tool/function call in a message"""

    id: str
    type: str = "function"
    function: Function

    class SQConfig:
        special_insert: bool = True

        def convert(obj):
            return ToolCall.model_dump_json(obj)

def embeddings_similarity(a: list, b: list):
    a = json.loads(a)
    b = json.loads(b)
    if not a or not b:
        return 0.
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

class ChatMessage(BaseModel):
    content: str = Field(default="")
    reasonong_content: Optional[str] = Field(default=None)
    tool_calls: Optional[List[ToolCall]] = Field(default=None)

class Message(BaseModel):
    """Represents a chat message in the conversation"""

    role: ROLE_TYPE = Field(...)  # type: ignore
    content: Optional[str] = Field(default=None)
    tool_calls: Optional[List[ToolCall]] = Field(default=None)
    name: Optional[str] = Field(default=None)
    tool_call_id: Optional[str] = Field(default=None)
    embeddings: Optional[str] = Field(default="[]") # [str(float)]
    uuid: str = Field(default="")
    time: float = Field(default=0.)

    @field_validator('tool_calls', mode="before")
    @classmethod
    def validate(cls, v):
        if isinstance(v, ToolCall):
            return v
        if v == None:
            return None 
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [json.loads(_t) for _t in json.loads(v)]

    def __add__(self, other) -> List["Message"]:
        """支持 Message + list 或 Message + Message 的操作"""
        if isinstance(other, list):
            if self.uuid in [m.uid for m in other]:
                return other
            return [self] + other
        elif isinstance(other, Message):
            if other.uuid == self.uuid:
                return [self]
            return [self, other]
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'"
            )

    def __radd__(self, other) -> List["Message"]:
        """支持 list + Message 的操作"""
        if isinstance(other, list):
            if self.uuid in [m.uid for m in other]:
                return other
            return other + [self]
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(other).__name__}' and '{type(self).__name__}'"
            )

    def __str__(self) -> str:
        message = {"role": self.role, "time": self.time}
        if self.content is not None:
            message["content"] = self.content
        if self.tool_calls is not None:
            message["tool_calls"] = [tool_call.model_dump() for tool_call in self.tool_calls]
        if self.name is not None:
            message["name"] = self.name
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        return str(message)

    def to_dict(self, all:bool = False) -> dict:
        """Convert message to dictionary format"""
        if all:
            message = {"role": self.role, "uuid": self.uuid, "time": self.time, "embeddings": self.embeddings}
        else:
            message = {"role": self.role}
        if self.content is not None:
            message["content"] = self.content
        if self.tool_calls is not None:
            message["tool_calls"] = [tool_call.model_dump() for tool_call in self.tool_calls]
        if self.name is not None:
            message["name"] = self.name
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        return message
    
    @property
    def sqlite_repr(self):
        return self.to_dict(all=True)

    @classmethod
    def user_message(cls, content: str) -> "Message":
        """Create a user message"""
        return cls(role=Role.USER, content=content)

    @classmethod
    def system_message(cls, content: str) -> "Message":
        """Create a system message"""
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def assistant_message(cls, content: Optional[str] = None) -> "Message":
        """Create an assistant message"""
        return cls(role=Role.ASSISTANT, content=content)

    @classmethod
    def tool_message(cls, content: str, name, tool_call_id: str = "") -> "Message":
        """Create a tool message"""
        return cls(
            role=Role.TOOL, content=content, name=name, tool_call_id=tool_call_id
        )

    @classmethod
    def from_tool_calls(
        cls, tool_calls: List[Any], content: Union[str, List[str]] = "", **kwargs
    ):
        """Create ToolCallsMessage from raw tool calls.

        Args:
            tool_calls: Raw tool calls from LLM
            content: Optional message content
        """
        formatted_calls = [
            {"id": call.id, "function": call.function.model_dump(), "type": "function"}
            for call in tool_calls
        ]
        return cls(
            role=Role.ASSISTANT, content=content, tool_calls=formatted_calls, **kwargs
        )


class Memory:
    messages: List[Message] = []
    max_messages: int = 100
    backend_db_file: str = ""

    def init(self, backend_db_file: str = ""):
        if not hasattr(self, "db"):
            self.db = DataBase()
        if backend_db_file:
            self.backend_db_file = backend_db_file
            if path.exists(self.backend_db_file):
                self.db.load(self.backend_db_file)
    def __init__(self, **kwargs):
        self.init(**kwargs)

    def add_message(self, message: Message) -> None:
        """Add to db"""
        if self.db:
            self.db.add("Message", message)
        """Add a message to memory"""
        self.messages.append(message)
        # Optional: Implement message limit
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def add_messages(self, messages: List[Message]) -> None:
        """Add to db"""
        if self.db:
            for msg in messages:
                self.db.add("Message", msg)
        """Add multiple messages to memory"""
        self.messages.extend(messages)

    def clear(self) -> None:
        """Clear all messages"""
        self.messages.clear()

    def get_recent_messages(self, n: int) -> List[Message]:
        """Get n most recent messages"""
        all_messages = self.messages
        if self.db:
            all_messages = [m for m in self.db("Message")]
        all_messages = sorted(all_messages, key=lambda m: m.time)
        return all_messages[-n:]
    
    def get_related_messages(self, msg: Message, n: int = 2) -> List[Message]:
        """Get n most related messages"""
        all_messages = self.messages
        if self.db:
            all_messages = [m for m in self.db("Message")]
        return sorted(all_messages, key=lambda m: embeddings_similarity(m.embeddings, msg.embeddings), reverse=True)[:n]

    def to_dict_list(self) -> List[dict]:
        """Convert messages to list of dicts"""
        return [msg.to_dict() for msg in self.messages]
    
    def close(self):
        if self.backend_db_file:
            self.db.save(self.backend_db_file)

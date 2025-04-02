from enum import Enum
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator
from pydantic_sqlite import DataBase
from datetime import datetime
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
            return json.dumps(v, ensure_ascii=False)


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
    base64_image: Optional[str] = Field(default=None)
    embeddings: Optional[str] = Field(default="[]") # [str(float)]
    time: int = Field(default=0)

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
            if self.time in [m.time for m in other]:
                return other
            return [self] + other
        elif isinstance(other, Message):
            if other.time == self.time:
                return [self]
            return [self, other]
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'"
            )

    def __radd__(self, other) -> List["Message"]:
        """支持 list + Message 的操作"""
        if isinstance(other, list):
            if self.time in [m.time for m in other]:
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
            message = {"role": self.role, "time": self.time, "embeddings": self.embeddings}
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
        if self.base64_image is not None:
            message["base64_image"] = self.base64_image
        return message

    @property
    def sqlite_repr(self):
        return self.to_dict(all=True)

    @classmethod
    def user_message(
        cls, content: str, base64_image: Optional[str] = None
    ) -> "Message":
        """Create a user message"""
        return cls(role=Role.USER, content=content, base64_image=base64_image)

    @classmethod
    def system_message(cls, content: str) -> "Message":
        """Create a system message"""
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def assistant_message(
        cls, content: Optional[str] = None, base64_image: Optional[str] = None
    ) -> "Message":
        """Create an assistant message"""
        return cls(role=Role.ASSISTANT, content=content, base64_image=base64_image)

    @classmethod
    def tool_message(
        cls, content: str, name, tool_call_id: str = "", base64_image: Optional[str] = None
    ) -> "Message":
        """Create a tool message"""
        return cls(
            role=Role.TOOL,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            base64_image=base64_image,
        )

    @classmethod
    def from_tool_calls(
        cls,
        tool_calls: List[Any],
        content: Union[str, List[str]] = "",
        base64_image: Optional[str] = None,
        **kwargs,
    ):
        """Create ToolCallsMessage from raw tool calls.

        Args:
            tool_calls: Raw tool calls from LLM
            content: Optional message content
            base64_image: Optional base64 encoded image
        """
        formatted_calls = [
            {"id": call.id, "function": call.function.model_dump(), "type": "function"}
            for call in tool_calls
        ]
        return cls(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=formatted_calls,
            base64_image=base64_image,
            **kwargs,
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
                self.messages = [m for m in self.db("Message")]

    def __init__(self, **kwargs):
        self.init(**kwargs)

    def add_message(self, message: Message) -> None:
        """Add to db"""
        if self.db:
            self.db.add("Message", message, pk = "time")
        """Add a message to memory"""
        self.messages.append(message)
        # Optional: Implement message limit
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def add_messages(self, messages: List[Message]) -> None:
        """Add to db"""
        if self.db:
            for msg in messages:
                self.db.add("Message", msg, pk = "time")
        """Add multiple messages to memory"""
        self.messages.extend(messages)

    def clear(self) -> None:
        """Clear all messages"""
        self.messages.clear()

    @staticmethod
    def _get_last_n_msgs(messages: List[Message], n: int):
        r = []
        c = 0
        tool_call_ids = []
        for m in messages[::-1]:
            if m.role == Role.TOOL:
                tool_call_ids.append(m.tool_call_id)
                r.insert(0, m)
                continue
            skip = False
            if m.tool_calls:
                for f in m.tool_calls:
                    if f.id in tool_call_ids:
                        tool_call_ids.remove(f.id)
                    else:
                        skip = True
            if skip:
                continue
            c += 1
            if c >= n:
                break
            r.insert(0, m)
        return r

    @staticmethod
    def _gen_context_msg(m: Message):
        return Message(role=Role.USER, content=f"releated:{m.content}, time:{str(datetime.fromtimestamp(m.time/1000.0))}")


    def get_recent_messages(self, n: int) -> List[Message]:
        """Get n most recent messages"""
        all_messages = self.messages
        # all_messages = sorted(all_messages, key=lambda m: m.time)
        return Memory._get_last_n_msgs(all_messages, n)

    def get_related_messages(self, msg: Message, n: int = 1) -> List[Message]:
        """Get n most related messages"""
        all_messages = self.messages
        mlist = sorted(all_messages, key=lambda m: embeddings_similarity(m.embeddings, msg.embeddings), reverse=True)[:n]
        return [ Memory._gen_context_msg(m) for m in mlist]

    def get_context_messages(self, msg: Message, n_recent: int, n_related: int = 1) -> List[Message]:
        """Get n most related messages"""
        all_messages = self.messages
        recent_list = Memory._get_last_n_msgs(all_messages, n_recent)
        related_list = sorted(all_messages, key=lambda m: embeddings_similarity(m.embeddings, msg.embeddings), reverse=True)[:n_related] if msg else []
        context_list = []
        for m in related_list:
            if not m in recent_list:
                context_list.append(Memory._gen_context_msg(m))
        context_list.extend(recent_list)
        return context_list

    def to_dict_list(self) -> List[dict]:
        """Convert messages to list of dicts"""
        return [msg.to_dict() for msg in self.messages]

    def close(self):
        if self.backend_db_file:
            self.db.save(self.backend_db_file)

from app.schema import AgentState
from app.tool.base import BaseTool, ToolResult
from app.tool.bash import Bash
from app.async_timer import AsyncTimer
from app.logger import logger
from datetime import datetime, timedelta

TIMER_ID_USER_NOTIFY = "notify"
class UserNotify(BaseTool):
    name: str = "user_notify"
    description: str = """Send a Notification to user later, used for reminder.*Note: Do not use this to reply*
Either notify_time or delay_minutes should be given to specify time to send notification.
The tool return execue result.
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "(required) The text of notification to send",
            },
            "notify_time": {
                "type": "string",
                "description": "(optional) The time when notification, must use `HH:MM`format, invalid time will be ignored. if set, delay_minutes has no effect"
            },
            "delay_minutes": {
                "type": "integer",
                "description": "(optional) The time(by minute) when notification to send from now. Default is 0.",
                "default": 0,
            },
        },
        "required": ["text"],
    }
    # wait: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        AsyncTimer.register_event(TIMER_ID_USER_NOTIFY, self.notify)

    async def execute(self, text: str, notify_time: str = "", delay_minutes: int = 0) -> ToolResult:
        """
        Execute a async notify task and return.

        Args:
            text (str): The text to send.
            delay_minutes (int, optional): The time of minute delay to notify. Default is 0.

        """
        now = datetime.now()
        timestamp = now.timestamp() + 60*delay_minutes # default fallback
        if notify_time:
            try:
                date = now.date()
                time = datetime.strptime(notify_time, "%H:%M").time()
                notify_datetime = datetime.combine(date, time)
                if notify_datetime < now:
                    notify_datetime += timedelta(days=1)
                timestamp = notify_datetime.timestamp()
            except ValueError:
                logger.info(f"Invalid time str:{notify_time}")
            finally:
                pass
        if delay_minutes == 0:
            self.agent.state = AgentState.FINISHED
            await self.notify(text)
        else:
            AsyncTimer.add_event(TIMER_ID_USER_NOTIFY, timestamp, {'text': text})
        return ToolResult(output="Notification successfully set")

    async def notify(self, text: str = ""):
        logger.info("exec notify")
        if text:
            bash = Bash()
            await bash.execute(f'notify-send -t 2000 -a "{self.agent.name}" "{text}"')
        if self.call_back:
            await self.call_back("Notification successfully send")

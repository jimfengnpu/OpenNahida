import asyncio
from asyncio import  CancelledError
from typing import List, Self
from datetime import datetime, timedelta

class AsyncTimer:
    timers: List[Self] = []

    def __init__(self, timeout, callback, **kwargs):
        self._due_time = 0.
        self._timeout = timeout
        self._callback = callback
        self._args = kwargs
        self._task = None

    def start(self):
        self._due_time = datetime.now().timestamp() + timedelta(seconds=self._timeout).total_seconds()
        self._task = asyncio.run_coroutine_threadsafe(self._job(), asyncio.get_event_loop())
        self._task.add_done_callback(self.on_finish)
        if not self in self.timers:
            self.timers.append(self)

    def __str__(self):
        return f"Timer {self._due_time} state:{self._task.done()}"

    async def _job(self):
        try:
            await asyncio.sleep(self._timeout)
            await self._callback(**self._args)
        except CancelledError as e:
            pass

    def on_finish(self, f):
        AsyncTimer.timers.remove(self)
        self._task = None

    def cancel(self) -> bool:
        if self._task:
            return self._task.cancel()
        return False

    @classmethod
    def cancel_all(cls):
        if cls.timers:
            for t in cls.timers.copy():
                t.cancel()

    @classmethod
    async def close(cls):
        cls.cancel_all()

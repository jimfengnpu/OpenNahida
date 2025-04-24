import asyncio
from asyncio import  CancelledError
from typing import List, Self
from datetime import datetime, timedelta
import json
from os import path

TIMER_STORE_FILE = "data/timers.json"
class AsyncTimer:
    timers: List[Self] = []
    call_backs = {}

    def __init__(self, timeout, callback_id, **kwargs):
        self._timeout = timeout
        self._due_time = datetime.now() + timedelta(seconds=self._timeout)
        self._callback_id = callback_id
        self._args = kwargs
        self._task = None

    @classmethod
    def init(cls):
        cls.restore_all()

    @classmethod
    def register_event(cls, call_back_id, call_back_exec):
        cls.call_backs[call_back_id] = call_back_exec

    @classmethod
    def add_event(cls, id, time, args = {}):
        current = datetime.now().timestamp()
        if time > current:
            t:Self = cls.__new__(cls)
            t.__init__(timeout=time - current, callback_id=id, **args)
            t._start()

    def _start(self):
        self._task = asyncio.run_coroutine_threadsafe(self._job(), asyncio.get_event_loop())
        if not self in self.timers:
            self.timers.append(self)

    def __repr__(self):
        return f"Timer {str(self._due_time)} state:{self._task.done() if self._task else True}"

    async def _job(self):
        try:
            await asyncio.sleep(self._timeout)
            _callback = self.call_backs.get(self._callback_id)
            if _callback:
                await _callback(**self._args)
        except CancelledError as e:
            pass
        finally:
            self.timers.remove(self)
            self._task = None

    def dump(self):
        return {
            "time": self._due_time.timestamp(),
            "id": self._callback_id,
            "args": self._args
        }

    def cancel(self) -> bool:
        if self._task:
            return self._task.cancel()
        return False

    @classmethod
    def dump_all(cls):
        dump_objs = []
        if cls.timers:
            for t in cls.timers:
                dump_objs.append(t.dump())
        with open(TIMER_STORE_FILE, "w") as f:
            f.write(json.dumps(dump_objs))

    @classmethod
    def restore_all(cls):
        timers_objs = []
        if path.exists(TIMER_STORE_FILE):
            with open(TIMER_STORE_FILE, "r") as f:
                timers_objs = json.loads(f.read())
        if timers_objs:
            for t in timers_objs:
                cls.add_event(**t)

    @classmethod
    def cancel_all(cls):
        if cls.timers:
            for t in cls.timers.copy():
                t.cancel()

    @classmethod
    async def close(cls):
        cls.dump_all()
        cls.cancel_all()

AsyncTimer.init()

import asyncio
from PriorityAsyncio import events


class PrioritizedEvent(asyncio.Event):
    
    def __init__(self, priority = None):
        super().__init__()
        self.priority = priority


    async def wait(self, priority = None):
        """Block until the internal flag is true.

        If the internal flag is true on entry, return True
        immediately.  Otherwise, block until another task calls
        set() to set the flag to true, then return True.
        """
        if self._value:
            return True

        self._loop = events.get_running_loop()
        fut = self._loop.create_future(priority = priority)
        self._waiters.append(fut)
        try:
            await fut
            return True
        finally:
            self._waiters.remove(fut)
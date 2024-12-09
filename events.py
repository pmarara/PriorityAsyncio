import asyncio
import heapq
import os
import threading
from asyncio import format_helpers

class _RunningLoop(threading.local):
    loop_pid = (None, None)

_running_loop = _RunningLoop()
_event_loop_policy = None
_lock = threading.Lock()

class PrioritizedHandle(asyncio.Handle):

    def __init__(self, callback, args, loop, priority, ag_name, context=None):
        super().__init__(callback, args, loop, context)
        self.priority = priority
        self.execounter = 0
        self.ag_name = ag_name
        self._when = None  

    # Método de comparación
    def __lt__(self, other):
        if self.priority == other.priority:
            return self.execounter < other.execounter
        else:
            return self.priority < other.priority


    @classmethod
    def from_handle(cls, handle):
        return PrioritizedHandle(handle._callback, handle._args, handle._loop, priority=0, ag_name=None, context=handle._context)


class PrioritizedTimerHandle(asyncio.TimerHandle):
    def __init__(self, when, callback, args, loop, priority, ag_name=None, context=None):
        super().__init__(when, callback, args, loop, context)
        self.priority = priority
        self.ag_name = ag_name
        self.execounter = 0


    # Método de comparación
    def __lt__(self, other):
        if self.priority == other.priority:
            if self._when is not None and other._when is not None and self._when != other._when:
                return self._when < other._when
            return self.execounter < other.execounter
        else:
            return self.priority < other.priority

    
    
def get_event_loop():
    """Return an asyncio event loop.

    When called from a coroutine or a callback (e.g. scheduled with call_soon
    or similar API), this function will always return the running event loop.

    If there is no running event loop set, the function will return
    the result of `get_event_loop_policy().get_event_loop()` call.
    """
    current_loop = asyncio._get_running_loop()
    if current_loop is not None:
        return current_loop
    return get_event_loop_policy().get_event_loop()    


def get_running_loop():
    """Return the running event loop.  Raise a RuntimeError if there is none.

    This function is thread-specific.
    """
    loop = asyncio._get_running_loop()
    if loop is None:
        raise RuntimeError('no running event loop')
    return loop


def get_event_loop_policy():
    """Get the current event loop policy."""
    if _event_loop_policy is None:
        _init_event_loop_policy()
    return _event_loop_policy


def _init_event_loop_policy():
    global _event_loop_policy
    with _lock:
        if _event_loop_policy is None:  
            from . import DefaultEventLoopPolicy
            _event_loop_policy = DefaultEventLoopPolicy()
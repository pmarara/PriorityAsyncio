import asyncio
import heapq
import os
import threading
from asyncio import format_helpers

# A TLS for the running event loop, used by _get_running_loop.
class _RunningLoop(threading.local):
    loop_pid = (None, None)

_running_loop = _RunningLoop()
_event_loop_policy = None
_lock = threading.Lock()

class PrioritizedHandle(asyncio.Handle):
    
    def __init__(self, callback, args, loop, priority, index, context=None):
        super().__init__(callback, args, loop, context=None)
        self.priority = priority
        self.index = index

    def __lt__(self, other):
        if self.priority == other.priority:
            return self.index < other.index
        else:
            return self.priority < other.priority
    
    def __gt__(self,other):
        if self.priority == other.priority:
            return self.index > other.index
        else:
            return self.priority > other.priority
    
    @classmethod
    def from_handle(cls, handle, index):
        return PrioritizedHandle(handle._callback, handle._args, handle._loop, priority = 0, index = index, context = handle._context )


    """
    def _run(self):
        try:
            print(self.priority)
            self._context.run(self._callback, priority=self.priority, *self._args)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            cb = format_helpers._format_callback_source(
                self._callback, self._args,
                debug=self._loop.get_debug())
            msg = f'Exception in callback {cb}'
            context = {
                'message': msg,
                'exception': exc,
                'handle': self,
            }
            if self._source_traceback:
                context['source_traceback'] = self._source_traceback
            self._loop.call_exception_handler(context)
        self = None  # Needed to break cycles when an exception occurs.
    """

class PrioritizedTimerHandle(asyncio.TimerHandle):
    def __init__(self, when, callback, args, loop, priority, index, context=None):
        super().__init__(when, callback, args, loop, context=None)
        self.priority = priority
        self.index = index

    def __lt__(self, other):
        if not getattr(self, "_when", False) and not getattr(other, "_when", False) and self._when != other._when:
            return self._when < other._when
        elif self.priority == other.priority:
            return self.index < other.index
        else:
            return self.priority < other.priority
    
    def __gt__(self,other):
        if not getattr(self, "_when", False) and not getattr(other, "_when", False) and self._when != other._when:
            return self._when > other._when
        elif self.priority == other.priority:
            return self.index > other.index
        else:
            return self.priority > other.priority
    
    
def get_event_loop():
    """Return an asyncio event loop.

    When called from a coroutine or a callback (e.g. scheduled with call_soon
    or similar API), this function will always return the running event loop.

    If there is no running event loop set, the function will return
    the result of `get_event_loop_policy().get_event_loop()` call.
    """
    # NOTE: this function is implemented in C (see _asynciomodule.c)
    current_loop = asyncio._get_running_loop()
    if current_loop is not None:
        return current_loop
    return get_event_loop_policy().get_event_loop()    

def get_running_loop():
    """Return the running event loop.  Raise a RuntimeError if there is none.

    This function is thread-specific.
    """
    # NOTE: this function is implemented in C (see _asynciomodule.c)
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
        if _event_loop_policy is None:  # pragma: no branch
            from . import DefaultEventLoopPolicy
            _event_loop_policy = DefaultEventLoopPolicy()
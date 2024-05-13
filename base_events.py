import asyncio
import heapq
from events import PrioritizedHandle, PrioritizedTimerHandle
from tasks import PrioritizedTask, ensure_future
from asyncio import coroutines, futures
from futures import PrioritizedFuture,  _get_loop
import inspect

_MIN_SCHEDULED_TIMER_HANDLES = 100
_MIN_CANCELLED_TIMER_HANDLES_FRACTION = 0.5
MAXIMUM_SELECT_TIMEOUT = 24 * 3600

class PrioritizedEventLoop(asyncio.SelectorEventLoop):


    def __init__(self):
        super().__init__()
        self._ready = []  #(priority queue)

    def call_soon(self, callback, *args, priority=None, context=None):
        self._check_closed()
        if self._debug:
            self._check_thread()
            self._check_callback(callback, 'call_soon')
        handle = self._call_soon(callback, args, priority, context)
        if handle._source_traceback:
            del handle._source_traceback[-1]
        return handle
    
    def _call_soon(self, callback, args, priority=None, context=None):
        if(priority == None):
            if(self._current_handle != None and getattr(self._current_handle, "priority") != None):
                priority = self._current_handle.priority
            else:
                priority = 0

        handle = PrioritizedHandle(callback, args, self, priority, context)
        if handle._source_traceback:
            del handle._source_traceback[-1]
        heapq.heappush(self._ready, handle)
        return handle
    
    def _add_callback(self, handle):
        if not handle._cancelled:
            heapq.heappush(self._ready, handle)

    def call_soon_threadsafe(self, callback, *args, priority, context=None):
        """Like call_soon(), but thread-safe."""
        self._check_closed()
        if self._debug:
            self._check_callback(callback, 'call_soon_threadsafe')
        handle = self._call_soon(callback, args, priority, context)
        if handle._source_traceback:
            del handle._source_traceback[-1]
        self._write_to_self()
        return handle

    def _run_once(self):
        """Run one full iteration of the event loop.

        This calls all currently ready callbacks, polls for I/O,
        schedules the resulting callbacks, and finally schedules
        'call_later' callbacks.
        """

        sched_count = len(self._scheduled)
        if (sched_count > _MIN_SCHEDULED_TIMER_HANDLES and
            self._timer_cancelled_count / sched_count >
                _MIN_CANCELLED_TIMER_HANDLES_FRACTION):
            # Remove delayed calls that were cancelled if their number
            # is too high
            new_scheduled = []
            for handle in self._scheduled:
                if handle._cancelled:
                    handle._scheduled = False
                else:
                    new_scheduled.append(handle)

            heapq.heapify(new_scheduled)
            self._scheduled = new_scheduled
            self._timer_cancelled_count = 0
        else:
            # Remove delayed calls that were cancelled from head of queue.
            while self._scheduled and self._scheduled[0]._cancelled:
                self._timer_cancelled_count -= 1
                handle = heapq.heappop(self._scheduled)
                handle._scheduled = False



        timeout = None
        if self._ready or self._stopping:
            timeout = 0
        elif self._scheduled:
            # Compute the desired timeout.
            timeout = self._scheduled[0]._when - self.time()
            if timeout > MAXIMUM_SELECT_TIMEOUT:
                timeout = MAXIMUM_SELECT_TIMEOUT
            elif timeout < 0:
                timeout = 0

        event_list = self._selector.select(timeout)
        self._process_events(event_list)
        # Needed to break cycles when an exception occurs.
        event_list = None

        # Handle 'later' callbacks that are ready.
        end_time = self.time() + self._clock_resolution
        while self._scheduled:
            handle = self._scheduled[0]
            if handle._when >= end_time:
                break
            handle = heapq.heappop(self._scheduled)
            handle._scheduled = False
            heapq.heappush(self._ready, handle)

        # This is the only place where callbacks are actually *called*.
        # All other places just add them to ready.
        # Note: We run all currently scheduled callbacks, but not any
        # callbacks scheduled by callbacks run this time around --
        # they will be run the next time (after another I/O poll).
        # Use an idiom that is thread-safe without using locks.
        ntodo = len(self._ready)
        for i in range(ntodo):
            handle = heapq.heappop(self._ready)
            #print(handle.priority)
            if handle._cancelled:
                continue
            if self._debug:
                try:
                    self._current_handle = handle
                    t0 = self.time()
                    handle._run()
                    dt = self.time() - t0
                finally:
                    self._current_handle = None
            else:
                self._current_handle = handle
                handle._run()
        handle = None  # Needed to break cycles when an exception occurs.

    def create_task(self, coro, priority=None, name=None, context=None):

        self._check_closed()
        if self._task_factory is None:
            if(priority == None):
                if(self._current_handle != None and getattr(self._current_handle, "priority") != None):
                    priority = self._current_handle.priority
                else:
                    priority = 0

            task = PrioritizedTask(coro, loop=self, priority=priority, name=name, context=context)
            if task._source_traceback:
                del task._source_traceback[-1]
        else:
            if context is None:
                # Use legacy API if context is not needed
                task = self._task_factory(self, coro)
            else:
                task = self._task_factory(self, coro, context=context)

            task.set_name(name)

        return task
        
    def call_at(self, when, callback, *args, priority=None, context=None):
            """Like call_later(), but uses an absolute time.

            Absolute time corresponds to the event loop's time() method.
            """
            if when is None:
                raise TypeError("when cannot be None")
            self._check_closed()
            if self._debug:
                self._check_thread()
                self._check_callback(callback, 'call_at')
            timer = PrioritizedTimerHandle(when, callback, args, self, priority, context)
            if timer._source_traceback:
                del timer._source_traceback[-1]
            heapq.heappush(self._scheduled, timer)
            timer._scheduled = True
            return timer
    
    def call_later(self, delay, callback, *args, priority=None, context=None):
        """Arrange for a callback to be called at a given time.

        Return a Handle: an opaque object with a cancel() method that
        can be used to cancel the call.

        The delay can be an int or float, expressed in seconds.  It is
        always relative to the current time.

        Each callback will be called exactly once.  If two callbacks
        are scheduled for exactly the same time, it is undefined which
        will be called first.

        Any positional arguments after the callback will be passed to
        the callback when it is called.
        """
        if delay is None:
            raise TypeError('delay must not be None')
        timer = self.call_at(self.time() + delay, callback, *args, priority = priority, context=context)
        if timer._source_traceback:
            del timer._source_traceback[-1]
        return timer
    
    def run_until_complete(self, future, priority=0):
        """Run until the Future is done.

        If the argument is a coroutine, it is wrapped in a Task.
s
        WARNING: It would be disastrous to call run_until_complete()
        with the same coroutine twice -- it would wrap it in two
        different Tasks and that can't be good.

        Return the Future's result, or raise its exception.
        """
        self._check_closed()
        self._check_running()

        new_task = not futures.isfuture(future)
        future = ensure_future(future, priority, loop=self)
        if new_task:
            # An exception is raised if the future didn't complete, so there
            # is no need to log the "destroy pending task" message
            future._log_destroy_pending = False

        future.add_done_callback(_run_until_complete_cb)
        try:
            self.run_forever()
        except:
            if new_task and future.done() and not future.cancelled():
                # The coroutine raised a BaseException. Consume the exception
                # to not log a warning, the caller doesn't have access to the
                # local task.
                future.exception()
            raise
        finally:
            future.remove_done_callback(_run_until_complete_cb)
        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')

        return future.result()
    
    def create_future(self, priority = None):
        """Create a Future object attached to the loop."""
        if(priority == None):
            if(self._current_handle != None and getattr(self._current_handle, "priority") != None):
                priority = self._current_handle.priority
            else:
                priority = 0
        
        return PrioritizedFuture(loop=self, priority = priority)
    
def _run_until_complete_cb(fut):
    if not fut.cancelled():
        exc = fut.exception()
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
            # Issue #22429: run_forever() already finished, no need to
            # stop it.
            return
    _get_loop(fut).stop()


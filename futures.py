import asyncio
from PriorityAsyncio import events
from asyncio import base_futures, exceptions, format_helpers
import sys
from types import GenericAlias
import reprlib
import contextvars


_PENDING = asyncio.base_futures._PENDING
_CANCELLED = asyncio.base_futures._CANCELLED
_FINISHED = asyncio.base_futures._FINISHED

_PyFuture = asyncio.Future

isfuture = base_futures.isfuture

class PrioritizedFuture:
    """This class is *almost* compatible with concurrent.futures.Future.

    Differences:

    - This class is not thread-safe.

    - result() and exception() do not take a timeout argument and
      raise an exception when the future isn't done yet.

    - Callbacks registered with add_done_callback() are always called
      via the event loop's call_soon().

    - This class is not compatible with the wait() and as_completed()
      methods in the concurrent.futures package.

    (In Python 3.4 or later we may be able to unify the implementations.)
    """

    _state = _PENDING
    _result = None
    _exception = None
    _loop = None
    _source_traceback = None
    _cancel_message = None
    _cancelled_exc = None

    _asyncio_future_blocking = False

    __log_traceback = False

    
    def __init__(self, priority, ag_name, *, loop=None):
        """Initialize the future.

        The optional event_loop argument allows explicitly setting the event
        loop object used by the future. If it's not provided, the future uses
        the default event loop.
        """
        if loop is None:
            self._loop = events.get_event_loop()
        else:
            self._loop = loop
        self._callbacks = []
        if self._loop.get_debug():
            self._source_traceback = format_helpers.extract_stack(
                sys._getframe(1))
            
        self.priority = priority
        self.ag_name = ag_name


    def __repr__(self):
        return _future_repr(self)
    

    def __del__(self):
        if not self.__log_traceback:
            return
        exc = self._exception
        context = {
            'message':
                f'{self.__class__.__name__} exception was never retrieved',
            'exception': exc,
            'future': self,
        }
        if self._source_traceback:
            context['source_traceback'] = self._source_traceback
        self._loop.call_exception_handler(context)

    __class_getitem__ = classmethod(GenericAlias)


    @property
    def _log_traceback(self):
        return self.__log_traceback


    @_log_traceback.setter
    def _log_traceback(self, val):
        if val:
            raise ValueError('_log_traceback can only be set to False')
        self.__log_traceback = False


    def get_loop(self):
        """Return the event loop the Future is bound to."""
        loop = self._loop
        if loop is None:
            raise RuntimeError("Future object is not initialized.")
        return loop


    def _make_cancelled_error(self):
        """Create the CancelledError to raise if the Future is cancelled.

        This should only be called once when handling a cancellation since
        it erases the saved context exception value.
        """
        if self._cancelled_exc is not None:
            exc = self._cancelled_exc
            self._cancelled_exc = None
            return exc

        if self._cancel_message is None:
            exc = exceptions.CancelledError()
        else:
            exc = exceptions.CancelledError(self._cancel_message)
        return exc
    

    def cancel(self, msg=None):
        """Cancel the future and schedule callbacks.

        If the future is already done or cancelled, return False.  Otherwise,
        change the future's state to cancelled, schedule the callbacks and
        return True.
        """
        self.__log_traceback = False
        if self._state != _PENDING:
            return False
        self._state = _CANCELLED
        self._cancel_message = msg
        self.__schedule_callbacks()
        return True


    def __schedule_callbacks(self):
        """Internal: Ask the event loop to call all callbacks.

        The callbacks are scheduled to be called as soon as possible. Also
        clears the callback list.
        """
        callbacks = self._callbacks[:]
        if not callbacks:
            return

        self._callbacks[:] = []
        for callback, ctx in callbacks:
            self._loop.call_soon(callback, self, priority=self.priority, ag_name= self.ag_name, context=ctx)


    def cancelled(self):
        """Return True if the future was cancelled."""
        return self._state == _CANCELLED


    def add_done_callback(self, fn, *, context=None):
        """Add a callback to be run when the future becomes done.

        The callback is called with a single argument - the future object. If
        the future is already done when this is called, the callback is
        scheduled with call_soon.
        """
        if self._state != _PENDING:
            self._loop.call_soon(fn, self, priority=self.priority, ag_name=self.ag_name, context=context)
        else:
            if context is None:
                context = contextvars.copy_context()
            self._callbacks.append((fn, context))


    def remove_done_callback(self, fn):
        """Remove all instances of a callback from the "call when done" list.

        Returns the number of callbacks removed.
        """
        filtered_callbacks = [(f, ctx)
                              for (f, ctx) in self._callbacks
                              if f != fn]
        removed_count = len(self._callbacks) - len(filtered_callbacks)
        if removed_count:
            self._callbacks[:] = filtered_callbacks
        return removed_count


    def result(self):
        """Return the result this future represents.

        If the future has been cancelled, raises CancelledError.  If the
        future's result isn't yet available, raises InvalidStateError.  If
        the future is done and has an exception set, this exception is raised.
        """
        if self._state == _CANCELLED:
            exc = self._make_cancelled_error()
            raise exc
        if self._state != _FINISHED:
            raise exceptions.InvalidStateError('Result is not ready.')
        self.__log_traceback = False
        if self._exception is not None:
            raise self._exception.with_traceback(self._exception_tb)
        return self._result
    

    def exception(self):
        """Return the exception that was set on this future.

        The exception (or None if no exception was set) is returned only if
        the future is done.  If the future has been cancelled, raises
        CancelledError.  If the future isn't done yet, raises
        InvalidStateError.
        """
        if self._state == _CANCELLED:
            exc = self._make_cancelled_error()
            raise exc
        if self._state != _FINISHED:
            raise exceptions.InvalidStateError('Exception is not set.')
        self.__log_traceback = False
        return self._exception


    def set_result(self, result):
        """Mark the future done and set its result.

        If the future is already done when this method is called, raises
        InvalidStateError.
        """
        if self._state != _PENDING:
            raise exceptions.InvalidStateError(f'{self._state}: {self!r}')
        self._result = result
        self._state = _FINISHED
        self.__schedule_callbacks()


    def set_exception(self, exception):
        """Mark the future done and set an exception.

        If the future is already done when this method is called, raises
        InvalidStateError.
        """
        if self._state != _PENDING:
            raise exceptions.InvalidStateError(f'{self._state}: {self!r}')
        if isinstance(exception, type):
            exception = exception()
        if isinstance(exception, StopIteration):
            new_exc = RuntimeError("StopIteration interacts badly with "
                                   "generators and cannot be raised into a "
                                   "Future")
            new_exc.__cause__ = exception
            new_exc.__context__ = exception
            exception = new_exc
        self._exception = exception
        self._exception_tb = exception.__traceback__
        self._state = _FINISHED
        self.__schedule_callbacks()
        self.__log_traceback = True


    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            yield self 
        if not self.done():
            raise RuntimeError("await wasn't used with future")
        return self.result()  
    

    def done(self):
        """Return True if the future is done.

        Done means either that a result / exception are available, or that the
        future was cancelled.
        """
        return self._state != _PENDING

    __iter__ = __await__ 


def _get_loop(fut):

    try:
        get_loop = fut.get_loop
    except AttributeError:
        pass
    else:
        return get_loop()
    return fut._loop


def _future_repr(future):
    info = ' '.join(_future_repr_info(future))
    return f'<{future.__class__.__name__} {info}>'


def _future_repr_info(future):
    """helper function for Future.__repr__"""
    info = [future._state.lower()]
    if future._state == _FINISHED:
        if future._exception is not None:
            info.append(f'exception={future._exception!r}')
        else:
            result = reprlib.repr(future._result)
            info.append(f'result={result}')
    if future._callbacks:
        info.append(_format_callbacks(future._callbacks))
    if future._source_traceback:
        frame = future._source_traceback[-1]
        info.append(f'created at {frame[0]}:{frame[1]}')
    return info


def _format_callbacks(cb):
    """helper function for Future.__repr__"""
    size = len(cb)
    if not size:
        cb = ''

    def format_cb(callback):
        return format_helpers._format_callback_source(callback, ())

    if size == 1:
        cb = format_cb(cb[0][0])
    elif size == 2:
        cb = '{}, {}'.format(format_cb(cb[0][0]), format_cb(cb[1][0]))
    elif size > 2:
        cb = '{}, <{} more>, {}'.format(format_cb(cb[0][0]),
                                        size - 2,
                                        format_cb(cb[-1][0]))
    return f'cb=[{cb}]'
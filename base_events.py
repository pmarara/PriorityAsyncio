import asyncio
import heapq
from PriorityAsyncio.events import PrioritizedHandle, PrioritizedTimerHandle
from PriorityAsyncio.tasks import PrioritizedTask, ensure_future
from PriorityAsyncio.futures import PrioritizedFuture,  _get_loop
from asyncio import coroutines, futures
import inspect
import selectors
import time
from collections import deque

_MIN_SCHEDULED_TIMER_HANDLES = 100
_MIN_CANCELLED_TIMER_HANDLES_FRACTION = 0.5
MAXIMUM_SELECT_TIMEOUT = 24 * 3600
TRACE_FILE = open("trace.ktr", "w")

isTrace = True # Especifica si se genera o no una traza para Kiwi

defined_lines = set()
defined_events = set()
header_lines = []
events_queue = deque()

class PrioritizedEventLoop(asyncio.SelectorEventLoop):

    def __init__(self):
        super().__init__()
        self._ready = []  # Cola de prioridad
        self.start_time = time.perf_counter()
        self.line_count = 0
        self._write_trace_header()
        self.arrival_counter = 0  # Contador para el orden de llegada de los eventos
        

    # Método que escribe la cabecera de la traza
    def _write_trace_header(self): 
        header_lines.append("DECIMAL_DIGITS 9\n")
        header_lines.append("DURATION 300\n")
        header_lines.append("PALETTE Rainbow\n")
        header_lines.append("ZOOM_X 16\n")
        header_lines.append("ZOOM_Y 10\n")
        header_lines.append("COLOR EXEC-E 0 orchid4\n\n")


    # Método que guarda nuevas líneas para la traza
    def _define_line_name(self, line_name, priority):
       if not any(line_name == line[0] and priority == line[1] for line in defined_lines):
            self.line_count += 1
            defined_lines.add((line_name, priority, self.arrival_counter))


    # Método que guarda los eventos
    def _log_event(self, event_type, handle, current_time, color=None):
        if self.line_count <= 99:
            priority = getattr(handle, 'priority', 0)
            agent_name = handle.ag_name if handle.ag_name != None else ""
            task_name = handle._callback.__name__ if hasattr(handle._callback, '__name__') else str(handle._callback)
            task_name = task_name.replace(" ", "_") 
            if agent_name.endswith("$"):
                line_name = f"{agent_name[:-1]}_p:{priority}"
            else:
                line_name = f"{agent_name}{task_name}_p:{priority}"  
            if  priority !=0: # Aquí se filtra qué eventos se quieren mostrar en la traza
                self._define_line_name(line_name, priority)
                defined_events.add((line_name, event_type, current_time, color))


    def call_soon(self, callback, *args, priority=None, ag_name=None, context=None):
        self._check_closed()
        if self._debug:
            self._check_thread()
            self._check_callback(callback, 'call_soon')
        handle = self._call_soon(callback, args, priority, ag_name, context)

        if isTrace:
            current_time = time.perf_counter() - self.start_time
            self._log_event('START', handle, current_time)
            self._log_event('READY-B', handle, current_time)

        if handle._source_traceback:
            del handle._source_traceback[-1]
        return handle
    

    def _call_soon(self, callback, args, priority=None, ag_name=None, context=None):
        if(priority == None):
            if(self._current_handle != None and getattr(self._current_handle, "priority") != None):
                priority = self._current_handle.priority
            else:
                priority = 0

        if(ag_name == None):
            if(self._current_handle != None and getattr(self._current_handle, "ag_name") != None):
                ag_name = self._current_handle.ag_name
            else:
                ag_name = None

        handle = PrioritizedHandle(callback, args, self, priority, ag_name, context)
        if handle._source_traceback:
            del handle._source_traceback[-1]
        heapq.heappush(self._ready, handle)
        return handle
    

    def _add_callback(self, handle):
        if not handle._cancelled:
            handle = PrioritizedHandle.from_handle(handle,)
            heapq.heappush(self._ready, handle)
            
        if isTrace:
            current_time = time.perf_counter() - self.start_time
            self._log_event('START', handle, current_time)
            self._log_event('READY-B', handle, current_time)


    def call_soon_threadsafe(self, callback, *args, priority = None, ag_name = None, context=None):
        """Like call_soon(), but thread-safe."""
        self._check_closed()
        if self._debug:
            self._check_callback(callback, 'call_soon_threadsafe')
        handle = self._call_soon(callback, args, priority, ag_name, context)
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
            while self._scheduled and self._scheduled[0]._cancelled:
                self._timer_cancelled_count -= 1
                handle = heapq.heappop(self._scheduled)
                handle._scheduled = False



        timeout = None
        if self._ready or self._stopping:
            timeout = 0
        elif self._scheduled:
            timeout = self._scheduled[0]._when - self.time()
            if timeout > MAXIMUM_SELECT_TIMEOUT:
                timeout = MAXIMUM_SELECT_TIMEOUT
            elif timeout < 0:
                timeout = 0

        event_list = self._selector.select(timeout)
        self._process_events(event_list)
        event_list = None


        end_time = self.time() + self._clock_resolution
        while self._scheduled:
            handle = self._scheduled[0]
            if handle._when >= end_time:
                break
            handle = heapq.heappop(self._scheduled)
            handle._scheduled = False
            heapq.heappush(self._ready, handle)

            if isTrace:
                current_time = time.perf_counter() - self.start_time
                self._log_event('START', handle, current_time)
                self._log_event('READY-B', handle, current_time)


        ntodo = len(self._ready)
        for i in range(ntodo):
            handle = heapq.heappop(self._ready)

            if handle._cancelled:
                continue
            if self._debug:
                try:
                    self._current_handle = handle
                    t0 = self.time()
                    handle._run()
                    handle.execounter += 1
                    dt = self.time() - t0

                finally:
                    self._current_handle = None
            else:
                self._current_handle = handle

                if isTrace:
                    current_time = time.perf_counter() - self.start_time
                    self._log_event('READY-E', handle, current_time)
                    self._log_event('EXEC-B', handle, current_time)
                
                try:
                    handle._run()
                    if isTrace:
                        current_time = time.perf_counter() - self.start_time
                        self._log_event('EXEC-E', handle, current_time)

                    handle.execounter += 1

                except Exception as e: 
                    print("EXCEPCION CAPTURADA: ", e)

        handle = None 


    def create_task(self, coro, priority=None, ag_name=None, context=None):

        self._check_closed()
        if self._task_factory is None:
            if(priority == None):
                if(self._current_handle != None and getattr(self._current_handle, "priority") != None):
                    priority = self._current_handle.priority
                else:
                    priority = 0

            if(ag_name == None):
                if(self._current_handle != None and getattr(self._current_handle, "ag_name") != None):
                    ag_name = self._current_handle.ag_name
                else:
                    ag_name = None

            task = PrioritizedTask(coro, loop=self, priority=priority, ag_name=ag_name, context=context)
            if task._source_traceback:
                del task._source_traceback[-1]
        else:
            if context is None:
                task = self._task_factory(self, coro)
            else:
                task = self._task_factory(self, coro, context=context)

        return task
        

    def call_at(self, when, callback, *args, priority=None, ag_name=None, context=None):
            """Like call_later(), but uses an absolute time.

            Absolute time corresponds to the event loop's time() method.
            """
            if(priority == None):
                if(self._current_handle != None and getattr(self._current_handle, "priority") != None):
                    priority = self._current_handle.priority
                else:
                    priority = 0

            if(ag_name == None):
                if(self._current_handle != None and getattr(self._current_handle, "ag_name") != None):
                    ag_name = self._current_handle.ag_name
                else:
                    ag_name = None

            if when is None:
                raise TypeError("when cannot be None")
            self._check_closed()
            if self._debug:
                self._check_thread()
                self._check_callback(callback, 'call_at')
            timer = PrioritizedTimerHandle(when, callback, args, self, priority, ag_name, context)
            if timer._source_traceback:
                del timer._source_traceback[-1]
            heapq.heappush(self._scheduled, timer)
            timer._scheduled = True
            return timer
    

    def call_later(self, delay, callback, *args, priority=None, ag_name=None, context=None):
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
        timer = self.call_at(self.time() + delay, callback, *args, priority = priority, ag_name=ag_name, context=context)

        if isTrace:
            current_time = time.perf_counter() - self.start_time            
            self._log_event('DEADLINE', timer, current_time)
            self._log_event('READY-B', timer, current_time)
            end_time = current_time + delay
            self._log_event('READY-E', timer, current_time = end_time)
            self._log_event('BLOCK', timer, current_time = end_time)

        if timer._source_traceback:
            del timer._source_traceback[-1]
        return timer
    

    def run_until_complete(self, future, priority=0):
        """Run until the Future is done.

        If the argument is a coroutine, it is wrapped in a Task.
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
            future._log_destroy_pending = False

        future.add_done_callback(_run_until_complete_cb)
        try:
            self.run_forever()
        except:
            if new_task and future.done() and not future.cancelled():

                future.exception()
            raise
        finally:
            future.remove_done_callback(_run_until_complete_cb)
        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')

        return future.result()
    
    def create_future(self, priority = None, ag_name = None):
        """Create a Future object attached to the loop."""
        if(priority == None):
            if(self._current_handle != None and getattr(self._current_handle, "priority") != None):
                priority = self._current_handle.priority
            else:
                priority = 0

        if(ag_name == None):
            if(self._current_handle != None and getattr(self._current_handle, "ag_name") != None):
                ag_name = self._current_handle.ag_name
            else:
                ag_name = None
        
        return PrioritizedFuture(loop=self, priority = priority, ag_name=ag_name)
    
    
def _run_until_complete_cb(fut):
    if not fut.cancelled():
        exc = fut.exception()
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):

            return
    _get_loop(fut).stop()


def write_trace_file():

    # Recorrer las distintas lineas que deben ir en la cabecera y asignar los números de linea a los eventos
    sorted_lines = sorted(defined_lines, key=lambda x: (x[1], x[0], x[2]))
    line_counter = 0
    for (line_name, _, _) in sorted_lines:
        header_lines.append(f"LINE_NAME {line_counter} {line_name}\n")
        for (line_name2, event_type, current_time, color) in defined_events:
            if line_name2 == line_name:
                log_event = f"{current_time:.9f} {event_type} {line_counter}"
                if color:
                    log_line += f" {color}"
                events_queue.append((current_time, log_event + "\n"))
        line_counter += 1


    # Ordenar eventos por tiempo antes de escribirlos en el archivo
    sorted_events = sorted(events_queue, key=lambda x: x[0])
    with open("trace.ktr", "w") as trace_file:
        trace_file.writelines(header_lines)
        for _, event in sorted_events:
            trace_file.write(event)

# Cerrar el archivo de traza al final del script
import atexit
atexit.register(write_trace_file)
atexit.register(TRACE_FILE.close)

from ..base_events import PrioritizedEventLoop
import asyncio

class DefaultEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    def __init__(self):
        super().__init__()

    def new_event_loop(self):
        return PrioritizedEventLoop()
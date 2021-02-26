import asyncio
from functools import partial
from logging import getLogger

try:
    from asyncio import get_running_loop
except ImportError:
    from asyncio import get_event_loop as get_running_loop


logger = getLogger(__name__)


try:
    from asyncio import run
except ImportError:
    def run(coro, debug=False):
        loop = asyncio.get_event_loop()
        if debug:
            loop.set_debug(True)
        loop.run_until_complete(coro)


try:
    from asyncio import create_task
except ImportError:
    def create_task(coro):
        loop = get_running_loop()
        return loop.create_task(coro)


try:
    from asyncio import to_thread
except ImportError:
    # asyncio.to_thread is available only in Python 3.9+
    async def to_thread(func, *args, **kwargs):
        loop = get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

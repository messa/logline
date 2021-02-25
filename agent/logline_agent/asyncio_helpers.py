from logging import getLogger


logger = getLogger(__name__)


try:
    from asyncio import run
except ImportError:
    def run(coro):
        from asyncio import get_event_loop
        loop = get_event_loop()
        loop.run_until_complete(coro)


try:
    from asyncio import create_task
except ImportError:
    def create_task(coro):
        from asyncio import get_event_loop
        loop = get_event_loop()
        return loop.create_task(coro)

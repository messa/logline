from argparse import ArgumentParser
from asyncio import run, sleep
from logging import getLogger


logger = getLogger(__name__)


def agent_main():
    p = ArgumentParser()
    p.add_argument('--scan')
    p.add_argument('--server')
    args = p.parse_args()
    run(async_main())


def setup_logging():
    from logging import basicConfig, DEBUG
    basicConfig(
        format='%(asctime)s [%(process)d] %(name)s %(levelname)5s: %(message)s',
        level=DEBUG)


async def async_main():
    while True:
        await sleep(60)

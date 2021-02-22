from argparse import ArgumentParser
from asyncio import run, sleep
from logging import getLogger


logger = getLogger(__name__)


def server_main():
    p = ArgumentParser()
    p.add_argument('--bind', default=':5645')
    p.add_argument('--dest', help='directory to store the received logs')
    args = p.parse_args()
    setup_logging()
    run(async_main())


def setup_logging():
    from logging import basicConfig, DEBUG
    basicConfig(
        format='%(asctime)s [%(process)d] %(name)s %(levelname)5s: %(message)s',
        level=DEBUG)


async def async_main():
    while True:
        await sleep(60)

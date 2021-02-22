from argparse import ArgumentParser
from asyncio import run
from logging import getLogger


logger = getLogger(__name__)


def server_main():
    p = ArgumentParser()
    args = p.parse_args()
    setup_logging()
    run(async_main())


def setup_logging():
    from logging import basicConfig, DEBUG
    basicConfig(
        format='%(asctime)s %(name)s %(levelname)5s: %(message)s',
        level=DEBUG)


async def async_main():
    pass

from argparse import ArgumentParser
from asyncio import run, sleep, create_task
from glob import glob
from logging import getLogger
from os import fstat
from pathlib import Path

from .configuration import Configuration
from .client import Client


logger = getLogger(__name__)


def agent_main():
    p = ArgumentParser()
    p.add_argument('--scan', action='append')
    p.add_argument('--server')
    args = p.parse_args()
    setup_logging()
    conf = Configuration(args=args)
    run(async_main(conf))


def setup_logging():
    from logging import basicConfig, DEBUG
    basicConfig(
        format='%(asctime)s [%(process)d] %(name)s %(levelname)5s: %(message)s',
        level=DEBUG)


async def async_main(conf):
    watched_paths = {}
    client = Client(conf.server_host, conf.server_port)
    while True:
        await scan_for_new_files(conf, watched_paths, new_path_callback=lambda p: create_task(watch_file(p, client=client)))
        await sleep(60)


async def scan_for_new_files(conf, watched_paths, new_path_callback):
    logger.debug('Scanning...')
    for glob_str in conf.scan_globs:
        #logger.debug('Scanning glob %s', glob_str)
        paths = glob(glob_str, recursive=True)
        for p in paths:
            p = Path(p).resolve()
            if str(p) not in watched_paths:
                #logger.debug('Found out new path %s from glob %s', p, glob_str)
                watched_paths[str(p)] = new_path_callback(p)


async def watch_file(file_path, client):
    last_inode = None
    while True:
        if file_path.stat().st_ino == last_inode:
            # No change, still the same file
            await sleep(5)
            continue
        f = file_path.open(mode='rb')
        f_inode = fstat(f.fileno()).st_ino
        if f_inode == last_inode:
            # This should generally never happen :)
            logger.warning('Detected inode change, but opened the same inode as before? %s', file_path)
            f.close()
            continue
        if last_inode is None:
            logger.info('Watching file: %s (inode: %s fd: %s)', file_path, f_inode, f.fileno())
        else:
            logger.info('File rotated: %s (inode: %s -> %s fd: %s)', file_path, last_inode, f_inode, f.fileno())
        create_task(send_file(file_path, f, client))
        last_inode = f_inode


async def send_file(file_path, file_stream, client):
    prefix = None
    while True:
        pos = file_stream.tell()
        chunk = file_stream.read(65536)
        assert isinstance(chunk, bytes)
        if not chunk:
            await sleep(1)
            continue
        logger.debug('Read %d bytes from %s (fd %s) position %s', len(chunk), file_path, file_stream.fileno(), pos)
        # get the prefix
        if not prefix:
            prefix = read_prefix(file_stream)
        # now send to the server :)
        await client.send_data(file_path, prefix, pos, chunk)


def read_prefix(f):
    pos = f.tell()
    try:
        f.seek(0)
        prefix = f.read(128)
    finally:
        f.seek(pos)
    assert f.tell() == pos
    return prefix

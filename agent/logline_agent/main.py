from argparse import ArgumentParser
from asyncio import run, sleep, create_task
from functools import partial
from glob import glob
from logging import getLogger
from os import fstat
from pathlib import Path

from .configuration import Configuration
from .client import connect_to_server


logger = getLogger(__name__)


def agent_main():
    p = ArgumentParser()
    p.add_argument('--conf', help='path to configuration file')
    p.add_argument('--log', help='path to log file')
    p.add_argument('--verbose', '-v', action='store_true')
    p.add_argument('--scan', action='append')
    p.add_argument('--server')
    p.add_argument('--tls', action='store_true')
    p.add_argument('--tls-cert', help='path to the file with certificate in PEM format')
    args = p.parse_args()
    setup_logging(verbose=args.verbose)
    conf = Configuration(args=args)
    setup_log_file(conf.log_file)
    run(async_main(conf))


log_format = '%(asctime)s [%(process)d] %(name)s %(levelname)5s: %(message)s'

own_log_files = set()

stderr_log_handler = None


def setup_logging(verbose):
    global stderr_log_handler
    from logging import DEBUG, INFO, getLogger, Formatter, StreamHandler
    h = StreamHandler()
    h.setFormatter(Formatter(log_format))
    h.setLevel(DEBUG if verbose else INFO)
    getLogger('').addHandler(h)
    getLogger('').setLevel(DEBUG)
    stderr_log_handler = h


def setup_log_file(log_file_path):
    global stderr_log_handler
    from logging import DEBUG, INFO, ERROR, getLogger, Formatter
    from logging.handlers import WatchedFileHandler
    if not log_file_path:
        return
    h = WatchedFileHandler(str(log_file_path))
    h.setFormatter(Formatter(log_format))
    h.setLevel(DEBUG)
    getLogger('').addHandler(h)
    own_log_files.add(Path(log_file_path).resolve())
    if stderr_log_handler:
        # decrease stderr handler level since we are logging into file instead
        if stderr_log_handler.level == INFO:
            stderr_log_handler.setLevel(ERROR)


async def async_main(conf):
    watched_paths = {}
    assert conf.server_host
    assert conf.server_port
    client_factory = partial(connect_to_server, conf=conf)
    while True:
        await scan_for_new_files(conf, watched_paths, new_path_callback=lambda p: create_task(watch_path(p, client_factory)))
        await sleep(1)


async def scan_for_new_files(conf, watched_paths, new_path_callback):
    #logger.debug('Scanning...')
    for glob_str in conf.scan_globs:
        #logger.debug('Scanning glob %s', glob_str)
        paths = glob(glob_str, recursive=True)
        for p in paths:
            p = Path(p).resolve()
            if str(p) not in watched_paths:
                #logger.debug('Found out new path %s from glob %s', p, glob_str)
                watched_paths[str(p)] = new_path_callback(p)


async def watch_path(file_path, client_factory):
    assert file_path == file_path.resolve()
    last_inode = None
    while True:
        if file_path.stat().st_ino == last_inode:
            # No change, still the same file
            if file_path in own_log_files:
                # do not process our own logfile too often to avoid too much noise
                await sleep(60)
            else:
                await sleep(1)
            continue
        f = file_path.open(mode='rb')
        f_inode = fstat(f.fileno()).st_ino
        if f_inode == last_inode:
            # This should generally never happen :)
            logger.warning('Detected inode change, but opened the same inode as before? %s', file_path)
            f.close()
            continue
        if last_inode is None:
            logger.info('Detected file: %s (inode: %s fd: %s)', file_path, f_inode, f.fileno())
        else:
            logger.info('File rotated: %s (inode: %s -> %s fd: %s)', file_path, last_inode, f_inode, f.fileno())
        create_task(follow_file(file_path, f, client_factory))
        last_inode = f_inode


async def follow_file(file_path, file_stream, client_factory):
    while True:
        try:
            while True:
                file_stream.seek(0)
                prefix = file_stream.read(50)
                if len(prefix) < 20:
                    logger.debug('File is too small: %s (fd: %s)', file_path, file_stream.fileno())
                    await sleep(10)
                    continue
                else:
                    break
            logger.debug('File %s (fd: %s) prefix: %r', file_path, file_stream.fileno(), prefix)
            assert prefix
            logger.debug('Connecting to server for file %s (fd: %s)', file_path, file_stream.fileno())
            client = await client_factory(log_path=file_path, log_prefix=prefix)
            try:
                server_length = client.header_reply['length']
                file_stream.seek(server_length)
                if file_stream.tell() != server_length:
                    logger.warning('Failed to seek %s (fd: %s) to %s - got to %s', file_path, file_stream.fileno(), server_length, file_stream.tell())
                    raise Exception(f"Failed to seek {file_path} to {server_length}")
                else:
                    logger.debug('Seeked %s (fd: %s) to %s', file_path, file_stream.fileno(), server_length)
                while True:
                    pos = file_stream.tell()
                    chunk = file_stream.read(2**20)
                    assert isinstance(chunk, bytes)
                    if not chunk:
                        # nothing was read
                        #logger.debug('No new content was read from %s (fd: %s) pos %s', file_path, file_stream.fileno(), pos)
                        await sleep(1)
                        continue
                    logger.debug('Read %d bytes from %s (fd: %s) position %s', len(chunk), file_path, file_stream.fileno(), pos)
                    await client.send_data(pos, chunk)
                    #logger.debug('client.send_data(%r, %r) done', pos, chunk)
            finally:
                client.close()
        except Exception as e:
            logger.exception('Failed to follow file %s (fd: %r): %r', file_path, file_stream.fileno(), e)
            await sleep(10)
            logger.info('Trying again to follow file %s (fd: %r)', file_path, file_stream.fileno())
            continue


def read_prefix(f):
    pos = f.tell()
    try:
        f.seek(0)
        prefix = f.read(128)
    finally:
        f.seek(pos)
    assert f.tell() == pos
    return prefix

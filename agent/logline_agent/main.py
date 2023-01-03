from argparse import ArgumentParser
from asyncio import sleep
from functools import partial
from glob import glob
from logging import getLogger
from os import fstat
from pathlib import Path
from time import monotonic as monotime

from .asyncio_helpers import run, create_task
from .configuration import Configuration
from .client import connect_to_server


logger = getLogger(__name__)


def get_argument_parser():
    p = ArgumentParser()
    p.add_argument('--conf', help='path to configuration file')
    p.add_argument('--log', help='path to log file')
    p.add_argument('--verbose', '-v', action='store_true')
    p.add_argument('--scan', action='append')
    p.add_argument('--server')
    p.add_argument('--tls', action='store_true')
    p.add_argument('--tls-cert', help='path to the file with certificate in PEM format')
    p.add_argument('--token-file', help='path to the file containing client token')
    return p


def agent_main():
    args = get_argument_parser().parse_args()
    setup_logging(verbose=args.verbose)
    conf = Configuration(args=args)
    setup_log_file(conf.log_file)
    logger.info('Logline Agent starting')
    try:
        run(async_main(conf), debug=True)
    except Exception as e:
        logger.exception('Logline Agent failed: %r', e)
    except BaseException as e:
        logger.info('Logline Agent stopping: %r', e)
    else:
        logger.info('Logline Agent done')


log_format = '%(asctime)s [%(process)d] %(name)-20s %(levelname)5s: %(message)s'

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
        for p in iter_files(conf):
            p_task = watched_paths.get(str(p))
            if p_task and p_task.done():
                logger.warning('Task for path %s is not running; task.exception: %r', p, p_task.exception())
                p_task = None
            if p_task is None:
                #logger.debug('Found out new path %s from glob %s', p, glob_str)
                watched_paths[str(p)] = create_task(watch_path(conf, p, client_factory))

        await sleep(conf.scan_new_files_interval)


def iter_files(conf):
    for glob_str in conf.scan_globs:
        paths = glob(glob_str, recursive=True)
        for p in paths:
            p = Path(p).resolve()
            yield p


async def watch_path(conf, file_path, client_factory):
    assert file_path == file_path.resolve()
    last_inode = None
    last_stat_log_message = None
    last_fd = None
    last_task = None
    while True:
        if last_task is not None and last_task.done():
            raise Exception(
                'Task for following file {} fd {} is not running; task.exception: {!r}'.format(
                    file_path, last_fd, last_task.exception()))

        try:
            current_inode = file_path.stat().st_ino
        except Exception as e:
            # Permissions error for example?
            if last_stat_log_message != repr(e):
                if isinstance(e, FileNotFoundError):
                    logger.info('File not found: %s', file_path)
                else:
                    logger.info('Could not stat %s: %r', file_path, e)
                last_stat_log_message = repr(e)
            await sleep(conf.tail_read_interval)
            continue
        else:
            last_stat_log_message = None

        if current_inode == last_inode:
            # No change, still the same file
            await sleep(conf.tail_read_interval)
            continue

        # File changed, open the new file
        f = file_path.open(mode='rb')
        f_inode = fstat(f.fileno()).st_ino
        if f_inode == last_inode:
            # This should generally never happen :)
            logger.warning('Detected inode change, but opened the same inode as before? %s', file_path)
            f.close()
            continue

        # Log some info
        if last_inode is None:
            logger.info('Detected file: %s (inode: %s fd: %s)', file_path, f_inode, f.fileno())
        else:
            logger.info('File rotated: %s (inode: %s -> %s fd: %s)', file_path, last_inode, f_inode, f.fileno())

        # Run follow_file() for this newly opened file
        last_inode = f_inode
        last_fd = f.fileno()
        last_task = create_task(follow_file(conf, file_path, f, f_inode, lambda: last_inode, client_factory))
        del f # opened file f will be closed in the just created task


async def follow_file(conf, file_path, file_stream, file_inode, get_current_inode, client_factory):
    last_data_read_timestamp = monotime()
    while True:
        try:
            file_too_small_last_logged_size = None
            while True:
                file_stream.seek(0)
                prefix = file_stream.read(conf.prefix_length)
                if len(prefix) < conf.min_prefix_length:
                    if file_too_small_last_logged_size != len(prefix):
                        logger.debug('File is too small (%d bytes): %s (fd: %s)', len(prefix), file_path, file_stream.fileno())
                        file_too_small_last_logged_size = len(prefix)
                    if file_inode != get_current_inode():
                        inactive_for = monotime() - last_data_read_timestamp
                        if inactive_for > conf.rotated_files_inactivity_threshold:
                            logger.debug(
                                'Rotated file %s (fd: %s) was inactive for %.3f s, closing',
                                file_path, file_stream.fileno(), inactive_for)
                            file_stream.close()
                            return
                    await sleep(conf.tail_read_interval)
                    continue
                else:
                    last_data_read_timestamp = monotime()
                    break
            logger.debug('File %s (fd: %s) prefix: %r', file_path, file_stream.fileno(), prefix)
            assert prefix
            logger.debug('Connecting to server for file %s (fd: %s)', file_path, file_stream.fileno())
            client = await client_factory(log_path=file_path, log_prefix=prefix)
            try:
                server_length = client.header_reply['length']
                file_stream.seek(server_length)
                if file_stream.tell() != server_length:
                    # This should never happen? Even seeks beyond file end work
                    # (that's how sparse files are created after all)
                    logger.warning('Failed to seek %s (fd: %s) to %s - got to %s', file_path, file_stream.fileno(), server_length, file_stream.tell())
                    raise Exception('Failed to seek {} to {}'.format(file_path, server_length))
                else:
                    logger.debug('Seeked %s (fd: %s) to %s', file_path, file_stream.fileno(), server_length)
                while True:
                    pos = file_stream.tell()
                    chunk = file_stream.read(2**20)
                    assert isinstance(chunk, bytes)
                    if not chunk:
                        # nothing was read
                        #logger.debug('No new content was read from %s (fd: %s) pos %s', file_path, file_stream.fileno(), pos)
                        if file_inode != get_current_inode():
                            inactive_for = monotime() - last_data_read_timestamp
                            if inactive_for > conf.rotated_files_inactivity_threshold:
                                logger.debug(
                                    'Rotated file %s (fd: %s) was inactive for %.3f s, closing',
                                    file_path, file_stream.fileno(), inactive_for)
                                file_stream.close()
                                return
                        await sleep(conf.tail_read_interval)
                        continue
                    last_data_read_timestamp = monotime()
                    logger.debug('Read %d bytes from %s (fd: %s) position %s', len(chunk), file_path, file_stream.fileno(), pos)
                    await client.send_data(pos, chunk)
                    #logger.debug('client.send_data(%r, %r) done', pos, chunk)
                    if file_path in own_log_files:
                        # do not process our own logfile too often to avoid too much noise
                        await sleep(60)
            finally:
                client.close()
        except Exception as e:
            logger.exception('Failed to follow file %s (fd: %r): %r', file_path, file_stream.fileno(), e)
            await sleep(10)
            logger.info('Trying again to follow file %s (fd: %r)', file_path, file_stream.fileno())
            continue

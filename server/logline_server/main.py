from argparse import ArgumentParser
from asyncio import run, sleep, start_server
from functools import partial
import json
from logging import getLogger
from reprlib import repr as smart_repr

from .configuration import Configuration


logger = getLogger(__name__)


def server_main():
    p = ArgumentParser()
    p.add_argument('--bind', default=':5645')
    p.add_argument('--dest', help='directory to store the received logs')
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
    server = await start_server(partial(handle_client, conf), conf.bind_host, conf.bind_port)
    logger.info('Listening on %s', ' '.join(str(s.getsockname()) for s in server.sockets))
    async with server:
        await server.serve_forever()


async def handle_client(conf, reader, writer):
    try:
        addr = writer.get_extra_info('peername')
        logger.info('New client: %s', addr)
        header = None
        while True:
            line = await reader.readline()
            logger.debug('Received: %s', smart_repr(line))
            command, meta_length, data_length = line.decode('ascii').split()
            meta_length = int(meta_length)
            data_length = int(data_length)
            meta_bytes = await reader.readexactly(meta_length)
            metadata = json.loads(meta_bytes)
            del meta_bytes
            logger.debug('Received %s metadata: %s', command, metadata)
            data = await reader.readexactly(data_length)
            if command == 'logline-agent-v1':
                if header:
                    raise Exception('Header already received')
                logger.debug('Received logline-agent-v1, replying with ok')
                header = metadata
                writer.write(b'ok 0\n')
                await writer.drain()
            elif command == 'save':
                if not header:
                    raise Exception('Header not received yet')
                await process_save(conf, header, metadata, data)
                writer.write(b'ok 0\n')
                await writer.drain()
            else:
                raise Exception(f'Unknown command: {command!r}')
    except Exception as e:
        logger.exception('Failed to handle client: %r', e)
    finally:
        logger.info('Closing connection')
        writer.close()


async def process_save(conf, header, metadata, data):
    logger.debug('process_save %r %d B', metadata, len(data))
    # process_save {'path': '/tmp/pytest-of-messa/pytest-119/test_existing_log_file_gets_co0/agent-src/sample.log', 'pos': 0, 'prefix': {'length': 13, 'sha1': 'R6AT5mDUCGGdiUsggGsdUIaqsDs='}} 13 B
    *dir_parts, filename = metadata['path'].strip('/').split('/')
    dst_path = conf.destination_directory / header['hostname'] / '~'.join(dir_parts) / filename
    logger.debug('dst_path: %s', dst_path)
    dst_path.parent.mkdir(exist_ok=True, parents=True)
    try:
        f = dst_path.open('rb+')
    except FileNotFoundError:
        logger.info('Creating new file: %s', dst_path)
        f = dst_path.open('wb+')
    f_prefix = f.read(metadata['prefix']['length'])
    if not f_prefix:
        if metadata['pos'] != 0:
            raise Exception('Our file is empty, but about to write from some offset')
    else:
        if len(f_prefix) != metadata['prefix']['length']:
            raise Exception('We have incomplete prefix')
        # TODO: check prefix
    f.seek(metadata['pos'])
    f.write(data)
    f.close()
    logger.debug('Wrote %d bytes to %s', len(data), dst_path)

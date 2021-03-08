from argparse import ArgumentParser
from asyncio import run, sleep, start_server
from base64 import b64encode
from datetime import datetime
from functools import partial
import gzip
import hashlib
from io import SEEK_END
import json
from logging import getLogger
import lzma
from reprlib import repr as smart_repr

from .configuration import Configuration
from .util import to_thread, decompress_zst


logger = getLogger(__name__)


def server_main():
    p = ArgumentParser()
    p.add_argument('--conf', help='path to configuration file')
    p.add_argument('--log', help='path to log file')
    p.add_argument('--verbose', '-v', action='store_true')
    p.add_argument('--bind')
    p.add_argument('--dest', help='directory to store the received logs')
    p.add_argument('--tls-cert', help='path to the file with certificate in PEM format')
    p.add_argument('--tls-key', help='path to the file with key in PEM format')
    p.add_argument('--tls-key-password-file', help='path to the file with key password in plaintext')
    p.add_argument('--client-token-hash', action='append')
    args = p.parse_args()
    setup_logging(verbose=args.verbose)
    conf = Configuration(args=args)
    setup_log_file(conf.log_file)
    run(async_main(conf))


log_format = '%(asctime)s [%(process)d] %(name)s %(levelname)5s: %(message)s'

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
    if stderr_log_handler:
        # decrease stderr handler level since we are logging into file instead
        if stderr_log_handler.level == INFO:
            stderr_log_handler.setLevel(ERROR)


async def async_main(conf):
    if conf.use_tls:
        from ssl import create_default_context, Purpose
        ssl_context = create_default_context(purpose=Purpose.CLIENT_AUTH)
        logger.debug('Using TLS; certfile: %s keyfile: %s', conf.tls_cert_file, conf.tls_key_file)
        ssl_context.load_cert_chain(
            certfile=conf.tls_cert_file,
            keyfile=conf.tls_key_file,
            password=conf.tls_password)
    else:
        ssl_context = None
    server = await start_server(
        partial(handle_client, conf),
        conf.bind_host, conf.bind_port,
        ssl=ssl_context)
    logger.info('Listening on %s', ' '.join(str(s.getsockname()) for s in server.sockets))
    async with server:
        await server.serve_forever()


async def handle_client(conf, reader, writer):
    f = None
    try:
        addr = writer.get_extra_info('peername')
        logger.info('New client has connected: %s', addr)
        command, metadata, data = await recv_command(reader)
        if command != 'logline-agent-v1' or data:
            raise Exception(f"Protocol error - received {smart_repr(command)} as first command")
        header = metadata
        assert header['hostname']
        assert header['path']
        assert header['prefix']
        assert header['auth']

        check_client_auth(conf, header.get('auth'))

        *dir_parts, filename = header['path'].strip('/').split('/')
        dst_path = conf.destination_directory / header['hostname'] / '~'.join(dir_parts) / filename

        if not dst_path.parent.is_dir():
            if not dst_path.parent.parent.is_dir():
                logger.debug('Creating directory: %s', dst_path.parent.parent)
                dst_path.parent.parent.mkdir()
            logger.debug('Creating directory: %s', dst_path.parent)
            dst_path.parent.mkdir()

        try:
            f = dst_path.open('rb+')
        except FileNotFoundError:
            f = None
            logger.debug('File does not exist yet: %s', dst_path)
        else:
            assert f.tell() == 0
            f_prefix = f.read(header['prefix']['length'])
            if f_prefix and sha1_b64(f_prefix) == header['prefix']['sha1']:
                # it's the correct file :)
                logger.info('File has the correct prefix: %s', dst_path)
            else:
                # need to create new file
                logger.info('File has different prefix, rotating: %s', dst_path)
                f.close()
                f = None
                iso_dt = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                dst_path.rename(dst_path.with_name(dst_path.name + f".rotated-{iso_dt}"))

        if not f:
            logger.info('Creating new file: %s', dst_path)
            f = dst_path.open('wb+')

        f.seek(0, SEEK_END)
        f_length = f.tell()

        await send_reply(writer, 'ok', {'length': f_length})

        while True:
            command, metadata, data = await recv_command(reader)
            if command != 'data':
                raise Exception(f"Protocol error - expected 'data', received {smart_repr(command)}")
            assert isinstance(data, bytes)
            if metadata.get('compression') == 'gzip':
                data = await to_thread(gzip.decompress, data)
            elif metadata.get('compression') == 'lzma':
                data = await to_thread(lzma.decompress, data)
            elif metadata.get('compression') == 'zst':
                data = await decompress_zst(data)
            elif metadata.get('compression') != None:
                raise Exception(f"Unsupported compression method: {metadata['compression']}")
            assert f.tell() == metadata['offset']
            logger.debug('Writing %d bytes at offset %s to file %s (fd: %s)', len(data), f.tell(), dst_path, f.fileno())
            f.write(data)
            f.flush()
            await send_reply(writer, 'ok', None)

    except ConnectionClosed:
        logger.info('Client closed connection')
    except Exception as e:
        logger.exception('Failed to handle client: %r', e)
    finally:
        logger.info('Closing connection')
        writer.close()
        if f:
            f.close()


class ConnectionClosed (Exception):
    pass


def check_client_auth(conf, header_auth):
    if not header_auth:
        raise Exception('No auth info received in header')
    if header_auth.get('client_token'):
        ct_bytes = header_auth['client_token'].encode('utf-8')
        if sha1_hex(ct_bytes) in conf.client_token_hashes:
            logger.debug('Client token verified with SHA1 hash %s', sha1_hex(ct_bytes))
            return
        raise Exception(f'Unknown client token; hash: {sha1_hex(ct_bytes)}')
    raise Exception(f'Client token was not received in header')


async def recv_command(reader):
    line = await reader.readline()
    if not line:
        raise ConnectionClosed()
    try:
        parts = line.decode('ascii').split()
    except UnicodeDecodeError:
        raise Exception(f"Failed to parse command line: {smart_repr(line)}")
    if len(parts) == 1:
        command, = parts
        return command, None, None
    if len(parts) == 2:
        command, metadata_size = parts
        if not metadata_size.isdigit():
            raise Exception(f"Failed to parse command line: {smart_repr(line)}")
        metadata_size = int(metadata_size)
        data_size = None
    elif len(parts) == 3:
        command, metadata_size, data_size = parts
        if not metadata_size.isdigit() or not data_size.isdigit():
            raise Exception(f"Failed to parse command line: {smart_repr(line)}")
        metadata_size = int(metadata_size)
        data_size = int(data_size)
    else:
        raise Exception(f"Failed to parse command line: {smart_repr(line)}")
    metadata_bytes = await reader.readexactly(metadata_size)
    metadata = json.loads(metadata_bytes)
    if data_size is None:
        data = None
    elif data_size == 0:
        data = b''
    else:
        data = await reader.readexactly(data_size)
    if data is None:
        logger.debug('Received %s %r', command, metadata)
    else:
        logger.debug('Received %s %r + %d B data', command, metadata, len(data))
    return command, metadata, data


async def send_reply(writer, status, payload):
    assert isinstance(status, str)
    if payload is None:
        writer.write(f'{status}\n'.encode('ascii'))
        logger.debug('Sent reply %s -', status)
    else:
        payload_bytes = json.dumps(payload).encode('utf-8')
        writer.write(f'{status} {len(payload_bytes)}\n'.encode('ascii'))
        writer.write(payload_bytes)
        logger.debug('Sent reply %s %r', status, payload)
    await writer.drain()


def sha1_b64(data):
    return b64encode(hashlib.sha1(data).digest()).decode('ascii')


assert sha1_b64(b'hello') == 'qvTGHdzF6KLavt4PO0gs2a6pQ00='


def sha1_hex(data):
    return hashlib.sha1(data).hexdigest()


assert sha1_hex(b'hello') == 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d'

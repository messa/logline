'''
Client for the Logline Server
'''

from asyncio import open_connection, wait_for
from base64 import b64encode
import gzip
from logging import getLogger
import re
from reprlib import repr as smart_repr
from socket import getfqdn
from time import monotonic as monotime
import json

from .asyncio_helpers import to_thread


logger = getLogger(__name__)

socket_timeout = 300


class ClientError (Exception):
    pass


async def connect_to_server(conf, log_path, log_prefix):
    '''
    Connect to the server specified in the configuration.
    Initial header is sent to the server, containing some metadata and log file prefix.
    '''
    assert isinstance(log_prefix, bytes)
    assert isinstance(conf.client_token, str)
    logger.debug('Connecting to %s:%s', conf.server_host, conf.server_port)
    if conf.use_tls:
        from ssl import create_default_context, Purpose
        logger.debug('Using TLS; cafile: %s', conf.tls_cert_file or '-')
        ssl_context = create_default_context(
            purpose=Purpose.SERVER_AUTH,
            cafile=str(conf.tls_cert_file) if conf.tls_cert_file else None)
    else:
        ssl_context = None
    reader, writer = await open_connection(conf.server_host, conf.server_port, ssl=ssl_context)
    cc = ClientConnection(reader, writer)
    await cc.send_header({
        'hostname': getfqdn(),
        'path': str(log_path),
        'prefix': {
            'length': len(log_prefix),
            'sha1': sha1_b64(log_prefix),
        },
        'auth': {
            'client_token': conf.client_token,
        },
    })
    assert cc.header_reply
    return cc


class ClientConnection:
    '''
    Use connect_to_server() to create instance of this class.
    '''

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.header_reply = None

    def close(self):
        self.writer.close()

    async def send_header(self, header):
        self.header_reply = await self._send_command('logline-agent-v1', header)

    async def send_data(self, offset, content):
        assert isinstance(offset, int)
        assert isinstance(content, bytes)
        metadata = {
            'offset': offset,
            'compression': None,
        }
        content_gz = await to_thread(gzip.compress, content)
        if len(content_gz) < len(content):
            metadata['compression'] = 'gzip'
            content = content_gz
        await self._send_command('data', metadata, content)

    async def _send_command(self, command, metadata, data=None):
        assert isinstance(command, str)
        assert isinstance(metadata, dict)
        md_json = json.dumps(metadata)
        md_json_safe = obfuscate_secrets(md_json)
        md_bytes = md_json.encode()
        md_bytes += b'\n'
        t0 = monotime()
        if data is None:
            logger.debug('Sending: %s %s', command, md_json_safe)
            self.writer.write('{} {}\n'.format(command, len(md_bytes)).encode('ascii'))
            self.writer.write(md_bytes)
        else:
            assert isinstance(data, bytes)
            logger.debug('Sending: %s %s + %d B data', command, md_json_safe, len(data))
            self.writer.write('{} {} {}\n'.format(command, len(md_bytes), len(data)).encode('ascii'))
            self.writer.write(md_bytes)
            self.writer.write(data)
        await wait_for(self.writer.drain(), timeout=socket_timeout)
        reply_line = await wait_for(self.reader.readline(), timeout=socket_timeout)
        #logger.debug('Received reply line %r', reply_line)
        reply_line_parts = reply_line.decode('ascii').split()
        if len(reply_line_parts) == 2:
            reply_status, reply_length = reply_line_parts
            reply_length = int(reply_length)
        else:
            reply_status, = reply_line_parts
            reply_length = 0
        if reply_length:
            reply_json = await wait_for(self.reader.readexactly(reply_length), timeout=socket_timeout)
            reply = json.loads(reply_json.decode('utf-8'))
            del reply_json
        else:
            reply = None
        duration_ms = int((monotime() - t0) * 1000)
        if reply_status == 'ok':
            logger.debug('Received reply in %d ms: %s %s', duration_ms, reply_status, '-' if reply is None else repr(reply))
            return reply
        elif reply_status == 'error':
            logger.warning('Received reply in %d ms: %s %s', duration_ms, reply_status, '-' if reply is None else repr(reply))
            raise ClientError('Error reply: {}'.format(reply))
        else:
            raise ClientError('Protocol error')


def sha1_b64(data):
    import hashlib
    assert isinstance(data, bytes)
    return b64encode(hashlib.sha1(data).digest()).decode('ascii')


assert sha1_b64(b'hello') == 'qvTGHdzF6KLavt4PO0gs2a6pQ00='


def obfuscate_secrets(json_str):
    assert isinstance(json_str, str)
    json_str = re.sub(r'("client_token":\s+"[^"]{2})([^"]+)([^"]{2}")', r'\1...\3', json_str, re.ASCII)
    return json_str


assert obfuscate_secrets('{"auth": {"client_token": "topsecret"}}') == '{"auth": {"client_token": "to...et"}}'

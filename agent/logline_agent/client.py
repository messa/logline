from asyncio import open_connection
from logging import getLogger
from reprlib import repr as smart_repr
from socket import getfqdn
import json


logger = getLogger(__name__)


async def connect_to_server(conf, server_host, server_port, log_path, log_prefix):
    assert isinstance(log_prefix, bytes)
    logger.debug('Connecting to %s:%s', server_host, server_port)
    if conf.tls:
        from ssl import create_default_context, Purpose
        logger.debug('Using TLS; cafile: %s', '-' if conf.tls_cert_file is None else conf.tls_cert_file)
        ssl_context = create_default_context(
            purpose=Purpose.SERVER_AUTH,
            cafile=conf.tls_cert_file)
    else:
        ssl_context = None
    reader, writer = await open_connection(server_host, server_port, ssl=ssl_context)
    cc = ClientConnection(reader, writer)
    await cc.send_header({
        'hostname': getfqdn(),
        'path': str(log_path),
        'prefix': {
            'length': len(log_prefix),
            'sha1': sha1_b64(log_prefix),
        },
    })
    assert cc.header_reply
    return cc


class ClientConnection:

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
        await self._send_command('data', metadata, content)

    async def _send_command(self, command, metadata, data=None):
        assert isinstance(command, str)
        assert isinstance(metadata, dict)
        md_bytes = json.dumps(metadata).encode()
        md_bytes += b'\n'
        if data is None:
            logger.debug('Sending: %s %s', command, metadata)
            self.writer.write(f'{command} {len(md_bytes)}\n'.encode('ascii'))
            self.writer.write(md_bytes)
        else:
            assert isinstance(data, bytes)
            logger.debug('Sending: %s %s + %d B data', command, metadata, len(data))
            self.writer.write(f'{command} {len(md_bytes)} {len(data)}\n'.encode('ascii'))
            self.writer.write(md_bytes)
            self.writer.write(data)
        await self.writer.drain()
        reply_line = await self.reader.readline()
        #logger.debug('Received reply line %r', reply_line)
        reply_line_parts = reply_line.decode('ascii').split()
        if len(reply_line_parts) == 2:
            reply_status, reply_length = reply_line_parts
            reply_length = int(reply_length)
        else:
            reply_status, = reply_line_parts
            reply_length = 0
        if reply_length:
            reply_json = await self.reader.readexactly(reply_length)
            reply = json.loads(reply_json)
            del reply_json
        else:
            reply = None
        if reply_status == 'ok':
            logger.debug('Received reply: %s %s', reply_status, '-' if reply is None else repr(reply))
            return reply
        elif reply_status == 'error':
            logger.warning('Received reply: %s %s', reply_status, '-' if reply is None else repr(reply))
            raise Exception(f'Error reply: {reply}')
        else:
            raise Exception('Protocol error')


def sha1_b64(data):
    import hashlib
    from base64 import b64encode
    return b64encode(hashlib.sha1(data).digest()).decode('ascii')


assert sha1_b64(b'hello') == 'qvTGHdzF6KLavt4PO0gs2a6pQ00='

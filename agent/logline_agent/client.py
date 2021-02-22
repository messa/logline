from asyncio import open_connection
from logging import getLogger
from reprlib import repr as smart_repr
from socket import getfqdn
import json


logger = getLogger(__name__)


class Client:
    '''
    Client for Logline Server
    '''

    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port

    async def send_data(self, file_path, prefix, pos, chunk):
        assert isinstance(prefix, bytes)
        assert isinstance(chunk, bytes)
        logger.debug('send_data(%s, %s, %s, %s)', file_path, smart_repr(prefix), pos, smart_repr(chunk))
        cc = await self._initiate_connection()
        metadata = {
            'path': str(file_path),
            'pos': pos,
            'prefix': {
                'length': len(prefix),
                'sha1': sha1_b64(prefix),
            },
        }
        await cc.send_command(b'save', metadata, chunk)

    async def _initiate_connection(self):
        reader, writer = await open_connection(self.server_host, self.server_port)
        cc = ClientConnection(reader, writer)
        header = {
            'hostname': getfqdn(),
        }
        reply = await cc.send_command(b'logline-agent-v1', header)
        return cc


def sha1_b64(data):
    import hashlib
    from base64 import b64encode
    return b64encode(hashlib.sha1(data).digest()).decode('ascii')


class ClientConnection:

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def send_command(self, command, metadata, data=b''):
        assert isinstance(command, bytes)
        assert isinstance(metadata, dict)
        assert isinstance(data, bytes)
        logger.debug('Sending command: %s %s %d B', command, metadata, len(data))
        md_bytes = json.dumps(metadata).encode()
        md_bytes += b'\n'
        self.writer.write(command)
        self.writer.write(f' {len(md_bytes)} {len(data)}\n'.encode('ascii'))
        self.writer.write(md_bytes)
        self.writer.write(data)
        await self.writer.drain()
        reply_line = await self.reader.readline()
        reply_status, reply_length = reply_line.decode().split()
        reply_length = int(reply_length)
        if reply_length:
            reply_json = await self.reader.readexactly(reply_length)
            reply = json.loads(reply_json)
        else:
            reply = {}
        if reply_status == 'ok':
            return reply
        elif reply_status == 'error':
            raise Exception(f'Error reply: {reply}')
        else:
            raise Exception('Protocol error')

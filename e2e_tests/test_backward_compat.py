'''
End-to-end backward-compatibility tests for the logline-agent-v1 wire protocol.

The other e2e tests (test_e2e.py, test_tls.py) launch the *current* logline-agent
binary against the *current* logline-server. They confirm that the two current
versions interoperate, but they do NOT protect against backward-incompatible
protocol changes: if the wire protocol is changed in both the agent and the
server at the same time, those tests keep passing even though an older agent
already deployed in the field would break.

These tests instead drive the current server with a small, self-contained
"frozen" implementation of the logline-agent-v1 protocol (see RawAgentV1 below).
That raw client deliberately does NOT import any agent code, so it stands in for
an older client. If a future change to the server breaks the v1 wire contract,
these tests should fail.

The protocol under test is documented in Protocol.md.
'''

from base64 import b64encode
from contextlib import ExitStack, contextmanager
import gzip
import hashlib
import json
from logging import getLogger
import lzma
import os
from pathlib import Path
import socket
from subprocess import Popen
from time import sleep
from time import monotonic as monotime


logger = getLogger(__name__)


client_token = 'topsecret'
client_token_hash = hashlib.sha1(client_token.encode()).hexdigest()


def sha1_b64(data):
    assert isinstance(data, bytes)
    return b64encode(hashlib.sha1(data).digest()).decode('ascii')


class ProtocolError (Exception):
    pass


class RawAgentV1:
    '''
    Minimal, frozen re-implementation of the logline-agent-v1 client protocol.

    This intentionally does not use any code from logline_agent so that it
    behaves like an older client speaking the original wire protocol. Do not
    "modernise" this class to track changes in the current agent - its whole
    purpose is to stay frozen and detect backward-incompatible server changes.
    '''

    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.rfile = self.sock.makefile('rb')
        self.header_reply = None

    def close(self):
        try:
            self.rfile.close()
        finally:
            self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _send_command(self, command, metadata, data=None):
        md_bytes = json.dumps(metadata).encode('utf-8') + b'\n'
        if data is None:
            self.sock.sendall('{} {}\n'.format(command, len(md_bytes)).encode('ascii'))
            self.sock.sendall(md_bytes)
        else:
            assert isinstance(data, bytes)
            self.sock.sendall('{} {} {}\n'.format(command, len(md_bytes), len(data)).encode('ascii'))
            self.sock.sendall(md_bytes)
            self.sock.sendall(data)
        return self._read_reply()

    def _read_reply(self):
        line = self.rfile.readline()
        if not line:
            raise ProtocolError('Connection closed by server while waiting for reply')
        parts = line.decode('ascii').split()
        if len(parts) == 2:
            status, length = parts[0], int(parts[1])
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        elif len(parts) == 1:
            status, payload = parts[0], None
        else:
            raise ProtocolError('Unexpected reply line: {!r}'.format(line))
        return status, payload

    def send_header(self, hostname, path, prefix, token=client_token):
        assert isinstance(prefix, bytes)
        status, payload = self._send_command('logline-agent-v1', {
            'hostname': hostname,
            'path': path,
            'prefix': {
                'length': len(prefix),
                'sha1': sha1_b64(prefix),
            },
            'auth': {
                'client_token': token,
            },
        })
        self.header_reply = (status, payload)
        return status, payload

    def send_data(self, offset, content, compression=None):
        assert isinstance(content, bytes)
        if compression == 'gzip':
            payload = gzip.compress(content)
        elif compression == 'lzma':
            payload = lzma.compress(content)
        elif compression is None:
            payload = content
        else:
            raise ValueError('Unsupported compression: {!r}'.format(compression))
        return self._send_command('data', {'offset': offset, 'compression': compression}, payload)


def terminate_process(p):
    if p.poll() is None:
        logger.info('Terminating process %s args: %s', p.pid, ' '.join(p.args))
        p.terminate()


@contextmanager
def running_server(dest_dir, port):
    server_cmd = [
        'logline-server',
        '--bind', f'127.0.0.1:{port}',
        '--dest', str(dest_dir),
        '--client-token-hash', client_token_hash,
    ]
    with ExitStack() as stack:
        server_process = stack.enter_context(Popen(server_cmd))
        stack.callback(terminate_process, server_process)
        # Wait until the server is accepting connections.
        t0 = monotime()
        while True:
            assert server_process.poll() is None
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=1):
                    break
            except OSError:
                if monotime() - t0 > 5:
                    raise Exception('Server did not start listening in time')
                sleep(.05)
        yield server_process


def dst_file_for(dest_dir, hostname, path):
    *dir_parts, filename = path.strip('/').split('/')
    mangled_dir = '~'.join(dir_parts)
    base = Path(dest_dir)
    if mangled_dir:
        return base / hostname / mangled_dir / filename
    return base / hostname / filename


def test_old_client_creates_new_file(tmp_path):
    '''An older client connecting for the first time should create the file.'''
    dest_dir = tmp_path / 'server-dst'
    dest_dir.mkdir()
    port = 9991
    hostname = 'oldclient.example.com'
    path = '/var/log/app/sample.log'
    content = b'2021-02-22 17:00:00 Hello from an old client\n'
    expected = dst_file_for(dest_dir, hostname, path)
    with running_server(dest_dir, port):
        with RawAgentV1('127.0.0.1', port) as agent:
            status, payload = agent.send_header(hostname, path, prefix=content)
            assert status == 'ok'
            # The header reply must carry the current length of the server file.
            assert payload == {'length': 0}
            status, payload = agent.send_data(0, content)
            assert status == 'ok'
            assert payload is None
    assert expected.read_bytes() == content


def test_old_client_resumes_from_server_offset(tmp_path):
    '''
    The server reports how much it already has; an older client must be able to
    send only the missing tail starting at that offset.
    '''
    dest_dir = tmp_path / 'server-dst'
    dest_dir.mkdir()
    port = 9992
    hostname = 'oldclient.example.com'
    path = '/var/log/app/resume.log'
    first = b'2021-02-22 17:00:00 first chunk\n'
    second = b'2021-02-22 17:00:01 second chunk\n'
    expected = dst_file_for(dest_dir, hostname, path)
    with running_server(dest_dir, port):
        with RawAgentV1('127.0.0.1', port) as agent:
            status, payload = agent.send_header(hostname, path, prefix=first)
            assert status == 'ok'
            assert payload == {'length': 0}
            assert agent.send_data(0, first)[0] == 'ok'
        assert expected.read_bytes() == first

        # Reconnect like an older client restarting: the server tells us the
        # current length and we resume from there.
        with RawAgentV1('127.0.0.1', port) as agent:
            status, payload = agent.send_header(hostname, path, prefix=first)
            assert status == 'ok'
            assert payload == {'length': len(first)}
            assert agent.send_data(payload['length'], second)[0] == 'ok'
    assert expected.read_bytes() == first + second


def test_old_client_triggers_rotation_on_prefix_mismatch(tmp_path):
    '''
    When the file beginning (prefix) no longer matches, the server must rotate
    the old file and start a fresh one - the behaviour older clients rely on.
    '''
    dest_dir = tmp_path / 'server-dst'
    dest_dir.mkdir()
    port = 9993
    hostname = 'oldclient.example.com'
    path = '/var/log/app/rotate.log'
    original = b'2021-02-22 17:10:00 original file\n'
    rotated = b'2021-02-22 17:20:00 brand new file\n'
    expected = dst_file_for(dest_dir, hostname, path)
    with running_server(dest_dir, port):
        with RawAgentV1('127.0.0.1', port) as agent:
            assert agent.send_header(hostname, path, prefix=original)[0] == 'ok'
            assert agent.send_data(0, original)[0] == 'ok'
        assert expected.read_bytes() == original

        # A new file with a different prefix must cause the server to rotate.
        with RawAgentV1('127.0.0.1', port) as agent:
            status, payload = agent.send_header(hostname, path, prefix=rotated)
            assert status == 'ok'
            assert payload == {'length': 0}
            assert agent.send_data(0, rotated)[0] == 'ok'
    assert expected.read_bytes() == rotated
    rotated_files = list(expected.parent.glob(expected.name + '.rotated-*'))
    assert len(rotated_files) == 1
    assert rotated_files[0].read_bytes() == original


def test_old_client_uncompressed_data(tmp_path):
    '''Older clients may send data with compression explicitly set to null.'''
    _check_compression(tmp_path, port=9994, compression=None)


def test_old_client_gzip_compression(tmp_path):
    '''gzip is part of the v1 protocol and must keep being decompressed.'''
    _check_compression(tmp_path, port=9995, compression='gzip')


def test_old_client_lzma_compression(tmp_path):
    '''lzma is part of the v1 protocol and must keep being decompressed.'''
    _check_compression(tmp_path, port=9996, compression='lzma')


def _check_compression(tmp_path, port, compression):
    dest_dir = tmp_path / 'server-dst'
    dest_dir.mkdir()
    hostname = 'oldclient.example.com'
    path = f'/var/log/app/{compression}.log'
    # Use repetitive content so that compression actually shrinks it.
    content = (b'2021-02-22 17:00:00 compressible log line\n' * 50)
    expected = dst_file_for(dest_dir, hostname, path)
    with running_server(dest_dir, port):
        with RawAgentV1('127.0.0.1', port) as agent:
            assert agent.send_header(hostname, path, prefix=content)[0] == 'ok'
            assert agent.send_data(0, content, compression=compression)[0] == 'ok'
    assert expected.read_bytes() == content

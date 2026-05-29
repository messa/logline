from contextlib import ExitStack
import hashlib
from logging import getLogger
import os
from pathlib import Path
from socket import getfqdn
from subprocess import Popen, check_call
from time import sleep
from time import monotonic as monotime


logger = getLogger(__name__)


client_token = 'topsecret'
client_token_hash = hashlib.sha1(client_token.encode()).hexdigest()


def mangle_src_path(src_dir):
    return str(Path(src_dir).resolve()).strip('/').replace('/', '~')


def test_run_agent_help():
    check_call(['logline-agent', '--help'])


def test_run_server_help():
    check_call(['logline-server', '--help'])


def test_existing_log_file_gets_copied(tmp_path, free_port):
    agent_src = tmp_path / 'agent-src'
    server_dst = tmp_path / 'server-dst'
    agent_src.mkdir()
    server_dst.mkdir()
    (agent_src / 'sample.log').write_text('2021-02-22 Hello world!\n')
    expected_dst_file = server_dst / getfqdn() / mangle_src_path(agent_src) / 'sample.log'
    port = free_port
    with ExitStack() as stack:
        agent_cmd = [
            'logline-agent',
            '--scan', str(agent_src / '*.log'),
            '--server', f'127.0.0.1:{port}',
        ]
        server_cmd = [
            'logline-server',
            '--bind', f'127.0.0.1:{port}',
            '--dest', str(server_dst),
            '--client-token-hash', client_token_hash,
        ]
        server_process = stack.enter_context(Popen(server_cmd))
        stack.callback(terminate_process, server_process)
        sleep(.1)
        agent_process = stack.enter_context(Popen(agent_cmd, env={**os.environ, 'CLIENT_TOKEN': client_token}))
        stack.callback(terminate_process, agent_process)
        t0 = monotime()
        sleep(.1)
        while True:
            logger.debug('Checking after %.2f s...', monotime() - t0)
            assert agent_process.poll() is None
            assert server_process.poll() is None
            check_call(['find', str(tmp_path)], stdout=2)
            if not expected_dst_file.exists():
                logger.debug('Still no file in %s', expected_dst_file)
            else:
                sleep(.1)
                # ^^^ sometimes the file exists, but is still empty, so sleep a little more
                assert expected_dst_file.read_text() == '2021-02-22 Hello world!\n'
                logger.debug('Destination file created! %s', expected_dst_file)
                break
            if monotime() - t0 > 2:
                raise Exception('Deadline exceeded')
            sleep(.2)


def test_log_file_update_gets_copied(tmp_path, free_port):
    agent_src = tmp_path / 'agent-src'
    server_dst = tmp_path / 'server-dst'
    agent_src.mkdir()
    server_dst.mkdir()
    (agent_src / 'sample.log').write_text('2021-02-22 Hello world!\n')
    expected_dst_file = server_dst / getfqdn() / mangle_src_path(agent_src) / 'sample.log'
    port = free_port
    with ExitStack() as stack:
        agent_cmd = [
            'logline-agent',
            '--scan', str(agent_src / '*.log'),
            '--server', f'127.0.0.1:{port}',
        ]
        server_cmd = [
            'logline-server',
            '--bind', f'127.0.0.1:{port}',
            '--dest', str(server_dst),
            '--client-token-hash', client_token_hash,
        ]
        server_process = stack.enter_context(Popen(server_cmd))
        stack.callback(terminate_process, server_process)
        sleep(.1)
        agent_process = stack.enter_context(Popen(agent_cmd, env={**os.environ, 'CLIENT_TOKEN': client_token}))
        stack.callback(terminate_process, agent_process)
        t0 = monotime()
        sleep(.1)
        while True:
            logger.debug('Checking after %.2f s...', monotime() - t0)
            assert agent_process.poll() is None
            assert server_process.poll() is None
            check_call(['find', str(tmp_path)], stdout=2)
            if not expected_dst_file.exists():
                logger.debug('Still no file in %s', expected_dst_file)
            else:
                sleep(.1)
                # ^^^ sometimes the file exists, but is still empty, so sleep a little more
                assert expected_dst_file.read_text() == '2021-02-22 Hello world!\n'
                logger.debug('Destination file created! %s', expected_dst_file)
                break
            if monotime() - t0 > 2:
                raise Exception('Deadline exceeded')
            sleep(.1)
        with (agent_src / 'sample.log').open(mode='a') as f:
            f.write('Second line\n')
        logger.info('File %s was appended', agent_src / 'sample.log')
        t0 = monotime()
        sleep(.1)
        while True:
            logger.debug('Checking after %.2f s...', monotime() - t0)
            assert agent_process.poll() is None
            assert server_process.poll() is None
            #check_call(['find', str(tmp_path)], stdout=2)
            assert expected_dst_file.exists()
            logger.debug('File %s contains: %r', expected_dst_file, expected_dst_file.read_text())
            if expected_dst_file.read_text() == '2021-02-22 Hello world!\nSecond line\n':
                logger.debug('Destination file updated! %s', expected_dst_file)
                break
            elif expected_dst_file.read_text() == '2021-02-22 Hello world!\n':
                logger.debug('Destination file not updated yet: %s', expected_dst_file)
            else:
                raise Exception(f"Unknown dst file {expected_dst_file} content: {expected_dst_file.read_text()!r}")
            if monotime() - t0 > 2:
                raise Exception('Deadline exceeded')
            sleep(.1)


def test_new_log_file_gets_copied(tmp_path, free_port):
    agent_src = tmp_path / 'agent-src'
    server_dst = tmp_path / 'server-dst'
    agent_src.mkdir()
    server_dst.mkdir()
    (agent_src / 'first.log').write_text('2021-02-22 17:00:00 First file\n')
    expected_dst_first_file = server_dst / getfqdn() / mangle_src_path(agent_src) / 'first.log'
    expected_dst_second_file = server_dst / getfqdn() / mangle_src_path(agent_src) / 'second.log'
    port = free_port
    with ExitStack() as stack:
        agent_cmd = [
            'logline-agent',
            '--scan', str(agent_src / '*.log'),
            '--server', f'127.0.0.1:{port}',
        ]
        server_cmd = [
            'logline-server',
            '--bind', f'127.0.0.1:{port}',
            '--dest', str(server_dst),
            '--client-token-hash', client_token_hash,
        ]
        server_process = stack.enter_context(Popen(server_cmd))
        stack.callback(terminate_process, server_process)
        sleep(.1)
        agent_process = stack.enter_context(Popen(agent_cmd, env={**os.environ, 'CLIENT_TOKEN': client_token}))
        stack.callback(terminate_process, agent_process)
        sleep(1)
        assert agent_process.poll() is None
        assert server_process.poll() is None
        assert expected_dst_first_file.exists()
        assert expected_dst_second_file.exists() == False
        (agent_src / 'second.log').write_text('2021-02-22 17:00:10 Second file\n')
        t0 = monotime()
        while True:
            logger.debug('Checking after %.2f s...', monotime() - t0)
            assert agent_process.poll() is None
            assert server_process.poll() is None
            check_call(['find', str(tmp_path)], stdout=2)
            if not expected_dst_second_file.exists():
                logger.debug('Still no file in %s', expected_dst_second_file)
            else:
                assert expected_dst_second_file.read_text() == '2021-02-22 17:00:10 Second file\n'
                logger.debug('Second destination file created! %s', expected_dst_second_file)
                break
            if monotime() - t0 > 2:
                raise Exception('Deadline exceeded')
            sleep(.2)


def test_rotate_log_file(tmp_path, free_port):
    agent_src = tmp_path / 'agent-src'
    server_dst = tmp_path / 'server-dst'
    agent_src.mkdir()
    server_dst.mkdir()
    (agent_src / 'sample.log').write_text('2021-02-22 17:10:00 First file\n')
    expected_dst_file = server_dst / getfqdn() / mangle_src_path(agent_src) / 'sample.log'
    port = free_port
    with ExitStack() as stack:
        agent_cmd = [
            'logline-agent',
            '--scan', str(agent_src / '*.log'),
            '--server', f'127.0.0.1:{port}',
        ]
        server_cmd = [
            'logline-server',
            '--bind', f'127.0.0.1:{port}',
            '--dest', str(server_dst),
            '--client-token-hash', client_token_hash,
        ]
        server_process = stack.enter_context(Popen(server_cmd))
        stack.callback(terminate_process, server_process)
        sleep(.1)
        agent_process = stack.enter_context(Popen(agent_cmd, env={**os.environ, 'CLIENT_TOKEN': client_token}))
        stack.callback(terminate_process, agent_process)
        sleep(.1)
        t0 = monotime()
        while True:
            logger.debug('Checking after %.2f s...', monotime() - t0)
            assert agent_process.poll() is None
            assert server_process.poll() is None
            check_call(['find', str(tmp_path)], stdout=2)
            if not expected_dst_file.exists():
                logger.debug('Still no file in %s', expected_dst_file)
            else:
                assert expected_dst_file.read_text() == '2021-02-22 17:10:00 First file\n'
                logger.debug('Destination file created! %s', expected_dst_file)
                break
            if monotime() - t0 > 2:
                raise Exception('Deadline exceeded')
            sleep(.1)
        (agent_src / 'sample.log').unlink()
        (agent_src / 'sample.log').write_text('2021-02-22 17:20:00 Second file\n')
        sleep(.1)
        t0 = monotime()
        while True:
            logger.debug('Checking after %.2f s...', monotime() - t0)
            assert agent_process.poll() is None
            assert server_process.poll() is None
            check_call(['find', str(tmp_path)], stdout=2)
            if not expected_dst_file.exists():
                logger.debug('Still no file in %s', expected_dst_file)
            else:
                if expected_dst_file.read_text() == '2021-02-22 17:20:00 Second file\n':
                    logger.debug('Destination file rotated! %s', expected_dst_file)
                    break
                else:
                    logger.debug('Destination file not rotated yet: %s', expected_dst_file)
            if monotime() - t0 > 2:
                raise Exception('Deadline exceeded')
            sleep(.1)


def terminate_process(p):
    if p.poll() is None:
        logger.info('Terminating process %s args: %s', p.pid, ' '.join(p.args))
        p.terminate()

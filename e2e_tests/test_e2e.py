from contextlib import ExitStack
from logging import getLogger
import os
from os import chdir
from pathlib import Path
from pytest import skip
from socket import getfqdn
from subprocess import Popen, check_call
import sys
from time import sleep
from time import monotonic as monotime


logger = getLogger(__name__)


def test_run_agent_help():
    check_call(['logline-agent', '--help'])


def test_run_server_help():
    check_call(['logline-server', '--help'])


def test_existing_log_file_gets_copied(tmp_path):
    chdir(tmp_path)
    Path('agent-src').mkdir()
    Path('server-dst').mkdir()
    Path('agent-src/sample.log').write_text('2021-02-22 Hello world!\n')
    mangled_src_path = str(Path('agent-src').resolve()).strip('/').replace('/', '~')
    expected_dst_file = Path('server-dst') / getfqdn() / mangled_src_path / 'sample.log'
    port = 9999
    with ExitStack() as stack:
        agent_cmd = [
            'logline-agent',
            '--scan', 'agent-src/*.log',
            '--server', f'127.0.0.1:{port}',
        ]
        server_cmd = [
            'logline-server',
            '--bind', f'127.0.0.1:{port}',
            '--dest', 'server-dst',
        ]
        server_process = stack.enter_context(Popen(server_cmd))
        stack.callback(terminate_process, server_process)
        sleep(.1)
        agent_process = stack.enter_context(Popen(agent_cmd))
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
                assert expected_dst_file.read_text() == '2021-02-22 Hello world!\n'
                logger.debug('Destination file created! %s', expected_dst_file)
                break
            if monotime() - t0 > 2:
                raise Exception('Deadline exceeded')
            sleep(.2)



def test_new_log_file_gets_copied(tmp_path):
    chdir(tmp_path)
    Path('agent-src').mkdir()
    Path('server-dst').mkdir()
    mangled_src_path = str(Path('agent-src').resolve()).strip('/').replace('/', '~')
    Path('agent-src/first.log').write_text('2021-02-22 17:00:00 First file\n')
    expected_dst_first_file = Path('server-dst') / getfqdn() / mangled_src_path / 'first.log'
    expected_dst_second_file = Path('server-dst') / getfqdn() / mangled_src_path / 'second.log'
    port = 9999
    with ExitStack() as stack:
        agent_cmd = [
            'logline-agent',
            '--scan', 'agent-src/*.log',
            '--server', f'127.0.0.1:{port}',
        ]
        server_cmd = [
            'logline-server',
            '--bind', f'127.0.0.1:{port}',
            '--dest', 'server-dst',
        ]
        server_process = stack.enter_context(Popen(server_cmd))
        stack.callback(terminate_process, server_process)
        sleep(.1)
        agent_process = stack.enter_context(Popen(agent_cmd))
        stack.callback(terminate_process, agent_process)
        sleep(1)
        assert agent_process.poll() is None
        assert server_process.poll() is None
        assert expected_dst_first_file.exists()
        assert expected_dst_second_file.exists() == False
        Path('agent-src/second.log').write_text('2021-02-22 17:00:10 Second file\n')
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



def terminate_process(p):
    if p.poll() is None:
        logger.info('Terminating process %s args: %s', p.pid, ' '.join(p.args))
        p.terminate()

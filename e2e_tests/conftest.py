import os
from pathlib import Path
import socket
import sys

from pytest import fixture


@fixture
def free_port():
    '''
    Allocate a free TCP port on the loopback interface.

    Each test gets its own port so that tests do not interfere with each
    other (or with a previous run still lingering in TIME_WAIT) through a
    shared, hard-coded port number.
    '''
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def pytest_configure(config):
    # Make sure the venv/bin directory is in PATH - in case this is running
    # from venv/bin/pytest without activating the venv first.
    bin_path = str(Path(sys.executable).parent)
    if bin_path not in os.environ['PATH'].split(':'):
        os.environ['PATH'] = f"{bin_path}:{os.environ['PATH']}"
        print('PATH modified to:', os.environ['PATH'])

    from logging import basicConfig, DEBUG
    basicConfig(
        format='%(asctime)s [pytest %(process)d] %(name)s %(levelname)5s: %(message)s',
        level=DEBUG)

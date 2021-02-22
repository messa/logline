import os
from pathlib import Path
import sys


def pytest_configure(config):
    # Make sure the venv/bin directory is in PATH - in case this is running
    # from venv/bin/pytest without activating the venv first.
    bin_path = str(Path(sys.executable).parent)
    if bin_path not in os.environ['PATH'].split(':'):
        os.environ['PATH'] = f"{bin_path}:{os.environ['PATH']}"
        print('PATH modified to:', os.environ['PATH'])

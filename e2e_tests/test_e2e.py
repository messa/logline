from contextlib import ExitStack
import os
from os import chdir
from pathlib import Path
from pytest import skip
from subprocess import Popen, check_call
import sys
from time import sleep


def test_run_agent_help():
    check_call(['logline-agent', '--help'])


def test_run_server_help():
    check_call(['logline-server', '--help'])


def test_e2e(tmp_path):
    chdir(tmp_path)
    with ExitStack() as stack:
        p_agent = stack.enter_context(Popen('logline-agent'))
        p_server = stack.enter_context(Popen('logline-server'))
        sleep(1)

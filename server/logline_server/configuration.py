from logging import getLogger
from pathlib import Path
import re


logger = getLogger(__name__)


class ConfigurationError (Exception):
    pass


class Configuration:

    def __init__(self, args):
        self.bind_host, self.bind_port = parse_address(args.bind)
        if args.dest:
            self.destination_directory = Path(args.dest)
        else:
            raise ConfigurationError('Destination directory not configured')


def parse_address(s):
    m = re.match(r'^([^:]+):([0-9]+)$', s)
    if m:
        host, port = m.groups()
        return host, int(port)
    m = re.match(r'^:?([0-9]+)$', s)
    if m:
        port, = m.groups()
        return '', int(port)
    raise Exception(f'Unknown address format: {s}')


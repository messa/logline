from logging import getLogger
import re


logger = getLogger(__name__)


class Configuration:

    def __init__(self, args):
        self.scan_globs = []
        self.scan_globs.extend(args.scan)
        logger.debug('scan_globs: %r', self.scan_globs)
        self.server_host, self.server_port = parse_address(args.server)


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


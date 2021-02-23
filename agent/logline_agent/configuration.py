from logging import getLogger
from pathlib import Path
import re


logger = getLogger(__name__)


class ConfigurationError (Exception):
    pass


class Configuration:

    def __init__(self, args):
        self.scan_globs = []
        if args.scan:
            self.scan_globs.extend(args.scan)
        if not self.scan_globs:
            raise ConfigurationError('No log sources were specified')
        logger.debug('scan_globs: %r', self.scan_globs)
        self.server_host, self.server_port = parse_address(args.server)
        self.tls = args.tls
        if self.tls:
            self.tls_cert_file = None
            if args.tls_cert:
                self.tls_cert_file = Path(args.tls_cert)


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


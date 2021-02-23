from logging import getLogger
import os
from pathlib import Path
import re


logger = getLogger(__name__)


class ConfigurationError (Exception):
    pass


class Configuration:

    def __init__(self, args):
        if args.log:
            self.log_file = Path(args.log)
        else:
            self.log_file = None
        self.bind_host, self.bind_port = parse_address(args.bind)
        if args.dest:
            self.destination_directory = Path(args.dest)
        else:
            raise ConfigurationError('Destination directory not configured')
        self.tls_cert_file = args.tls_cert
        self.tls_key_file = args.tls_key
        if args.tls_key_password_file:
            self.tls_password = Path(args.tls_key_password_file).read_text().strip()
        else:
            self.tls_password = os.environ.get('TLS_KEY_PASSWORD')
        self.tls = bool(self.tls_cert_file)


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


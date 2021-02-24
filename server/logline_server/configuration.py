from logging import getLogger
import os
from pathlib import Path
import re


logger = getLogger(__name__)


class ConfigurationError (Exception):
    '''
    This exception means that some user input is missing.
    '''


class Configuration:
    '''
    Logline Server configuration
    '''

    default_port = 5645

    def __init__(self, args):
        if args.conf:
            cfg_path = Path(args.conf)
        elif os.environ.get('CONF'):
            cfg_path = Path(os.environ['CONF'])
        else:
            cfg_path = None

        if cfg_path:
            cfg_dir = cfg_path.parent
            import yaml
            cfg = yaml.safe_load(cfg_path.read_text())
        else:
            cfg = {}

        if args.log:
            self.log_file = Path(args.log)
        elif cfg.get('log', {}).get('file'):
            self.log_file = cfg_dir / cfg['log']['file']
        else:
            self.log_file = None

        if args.bind:
            self.bind_host, self.bind_port = parse_address(args.bind)
        elif cfg.get('bind'):
            self.bind_host, self.bind_port = parse_address(cfg['bind'])
        else:
            self.bind_host, self.bind_port = '', self.default_port

        if args.dest:
            self.destination_directory = Path(args.dest)
        elif cfg.get('dsst'):
            self.destination_directory = cfg_dir / cfg['dest']
        else:
            raise ConfigurationError('Destination directory not configured')

        if args.tls_cert:
            self.tls_cert_file = args.tls_cert
        elif cfg.get('tls', {}).get('cert'):
            self.tls_cert_file = cfg_dir / cfg['tls']['cert']
        else:
            self.tls_cert_file = None

        if args.tls_key:
            self.tls_key_file = args.tls_key
        elif cfg.get('tls', {}).get('key'):
            self.tls_key_file = cfg['tls']['key']
        else:
            self.tls_key_file = None

        if args.tls_key_password_file:
            self.tls_password = Path(args.tls_key_password_file).read_text().strip()
        elif cfg.get('tls', {}).get('key_password_file'):
            self.tls_password = (cfg_dir / cfg['tls']['key_password_file']).read_text().strip()
        elif cfg.get('tls', {}).get('key_password'):
            self.tls_password = cfg['tls']['key_password']
        elif os.environ.get('TLS_KEY_PASSWORD'):
            self.tls_password = os.environ['TLS_KEY_PASSWORD']

        self.use_tls = bool(self.tls_cert_file)


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


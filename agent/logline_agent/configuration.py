from logging import getLogger
from pathlib import Path
import re


logger = getLogger(__name__)


class ConfigurationError (Exception):
    '''
    This exception means that some user input is missing.
    '''


class Configuration:
    '''
    LogLine Agent configuration
    '''

    def __init__(self, args):
        if args.conf:
            cfg_path = Path(args.conf)
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

        self.scan_globs = []
        if args.scan:
            self.scan_globs.extend(args.scan)
        if cfg.get('scan'):
            assert isinstance(cfg['scan'], list)
            self.scan_globs.extend(cfg['scan'])
        logger.debug('scan_globs: %r', self.scan_globs)
        if not self.scan_globs:
            raise ConfigurationError('No log sources were configured')

        if args.server:
            self.server_host, self.server_port = parse_address(args.server)
        elif cfg.get('server'):
            self.server_host, self.server_port = parse_address(cfg['server'])
        else:
            raise ConfigurationError('No server address configured')

        if args.tls_cert:
            self.tls_cert_file = args.tls_cert
        elif cfg.get('tls', {}).get('cert'):
            self.tls_cert_file = cfg_dir / cfg['tls']['cert']
        else:
            self.tls_cert_file = None

        self.use_tls = args.tls \
            or self.tls_cert_file \
            or cfg.get('tls', {}).get('enable') \
            or cfg.get('tls', {}).get('enabled')


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


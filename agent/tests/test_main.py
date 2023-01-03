from logline_agent.configuration import Configuration
from logline_agent.main import get_argument_parser, iter_files

from pytest import fixture


@fixture
def load_conf(temp_dir):
    def load_conf(conf_yaml):
        (temp_dir / 'configuration.yaml').write_text(conf_yaml)
        args = get_argument_parser().parse_args(['--conf', str(temp_dir / 'configuration.yaml')])
        conf = Configuration(args=args)
        return conf
    return load_conf


def test_iter_files(temp_dir, load_conf):
    conf = load_conf(f'''\
        server: 127.0.0.1:9999
        client_token: topsecret
        scan:
          - {temp_dir}/*/*.log
        exclude:
          - {temp_dir}/excluded/not_this.log
    ''')
    assert list(iter_files(conf)) == []
    (temp_dir / 'log').mkdir()
    (temp_dir / 'log' / 'example.log').write_text('Hello World!\n')
    (temp_dir / 'excluded').mkdir()
    (temp_dir / 'excluded' / 'not_this.log').write_text('This file should be excluded\n')
    assert list(iter_files(conf)) == [(temp_dir / 'log' / 'example.log')]

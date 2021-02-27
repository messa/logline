from contextlib import ExitStack
import hashlib
from logging import getLogger
import os
from os import chdir
from pathlib import Path
from pytest import skip
from socket import getfqdn
from subprocess import Popen, check_call
import sys
from textwrap import dedent
from time import sleep
from time import monotonic as monotime


logger = getLogger(__name__)


client_token = 'topsecret'
client_token_hash = hashlib.sha1(client_token.encode()).hexdigest()


selfsigned_cert_pem = dedent('''\
    -----BEGIN CERTIFICATE-----
    MIIFrzCCA5egAwIBAgIUUsSq5jEK6ktEblY7XJsMzD8OKJswDQYJKoZIhvcNAQEL
    BQAwZjELMAkGA1UEBhMCQ1oxDzANBgNVBAgMBlByYWd1ZTEPMA0GA1UEBwwGUHJh
    Z3VlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQxEjAQBgNVBAMM
    CWxvY2FsaG9zdDAgFw0yMTAyMjIxNzMwNTlaGA8yMTIxMDEyOTE3MzA1OVowZjEL
    MAkGA1UEBhMCQ1oxDzANBgNVBAgMBlByYWd1ZTEPMA0GA1UEBwwGUHJhZ3VlMSEw
    HwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQxEjAQBgNVBAMMCWxvY2Fs
    aG9zdDCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBANi7xF7kMz6HFCXK
    L5eeP8tBFoYFidClDKBFc3z1nmn+TxoJ2/9FzcLZ80mNIC+Le28OBiIFPNYzerMp
    9FduZK9zQCWP8fBCWyljwXsKuT6KXbDO0Z+2zOQeLuV5zrLZXBDWkVkpXau0rQr/
    sHKbAnKuL60gcIouwDtPhywByKC4JXglYg+3MTBWq3Ds1+OrNaYlOV9M9T+Tb5W9
    l7VDbDJRs4EFa028ugkGdN/J0RjJ2vfF+VUbCaHNkMAMHeGd/KaZI/G3ko5p8Nyn
    v7XdKHts21Pvu7/QCgcHxXdwEkRNJpnazceVWttX77yq/3xk9qNsdKt9xOW14U/A
    tSU7fJG39Mxg7ZOfQ2cd8PIJ/w/Ev8YBGCnIyLPsvVPEYlRPkugBTMX07DpBNewt
    R/WfLiqtBiNZqAv9tYH0yIxvdGYgVp9XiuJVreU2XXHROecE0tHL3vsX9kiEEMi1
    DMIINmx3nj3Pup+IPvnwsB1NaVYVn8umd757VOZNBO9niAZXjDoR3XByZn+uT1/L
    QRF80/tvG0pf1FQ7G2WlwOKWKDgDBzbpmJMJaw/r/lS3v0kfDd5nqNDPrrZRra00
    +v7Ttq2Wad3/hyhtcR3mao5H3GnQOlCWASE3F95W7aeSfPWs6vPDHZsWxYbAz+a/
    2n3G11u++n6FdiZQrJbcBAi7gec5AgMBAAGjUzBRMB0GA1UdDgQWBBTuQ0O+o01Y
    SWbUIuDq449drg2oiTAfBgNVHSMEGDAWgBTuQ0O+o01YSWbUIuDq449drg2oiTAP
    BgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4ICAQBSNiheXcTQYNgAfLsc
    mT3a7KO6Q1iXGClmQ4p8PTn8L4kExazZBFebWhB3eDgeJavZZF2X3ppVYxvYNPph
    EAdB1sV/i/fubZTvQS7Ep8DZuAmsfq52+1BtAepW/7zn+SZ6oONuLdaJAbCfp6Ex
    UkaxrMv/Q3QS4tHhlxjAo6mdD88qVqfT4bSy+ns0ohS8/tbrxZwbYzyFnb0bDg+a
    MUqxo/Bzzulc7d4rfApE5K0WmwdrKSE/nZ9q+wu1yBKB1g3EPxfb+AlniYtct2iS
    nsE0q/St/x8VN3Ef777K1FMkfXlB9j7yYCnkfdVugadG90vk9hBI6xlvyzK3p3XJ
    wnCQeJZQsHlCJTTdNW4fsG5SHa2Bajj5a2LgZAUzdQjSOPKkCc6sDH+MO8kVSL78
    Gwslb5biGudu1104eySZYskp2u7mA5KlyHbW52TK4aVwD/q1Sl1Q9O97j3NKxebl
    IE/C/BYGz6lHWEIiehM40UJLG/wtwJ/2bMe/uezfV3GbJxeeQsZW8fyPCFfftqlb
    ADvoL3ZZwn/Ijyzixwkv16CISANxCsWwBle6jX7ZzwQdqxg9CdryvhHzSZ2lZzE6
    yCQvkoMxyHAcKXBcNR5npYOAZGgSWqDnXtngdn9vaEA6kottxq/1LYfqx7+jl77A
    YoYCfZzCuTsDHSne0RqB8uuFhw==
    -----END CERTIFICATE-----
''')


selfsigned_key_pem = dedent('''\
    -----BEGIN ENCRYPTED PRIVATE KEY-----
    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
    dyn/nhnXkSnN78K0EJEm4Yruh0sdr6jN
    -----END ENCRYPTED PRIVATE KEY-----
''')


selfsigned_key_password = 'topsecret'


def test_send_log_file_over_tls(tmp_path):
    chdir(tmp_path)
    Path('cert.pem').write_text(selfsigned_cert_pem)
    Path('key.pem').write_text(selfsigned_key_pem)
    Path('agent-src').mkdir()
    Path('server-dst').mkdir()
    Path('agent-src/sample.log').write_text('2021-02-22 Hello world!\n')
    mangled_src_path = str(Path('agent-src').resolve()).strip('/').replace('/', '~')
    expected_dst_file = Path('server-dst') / getfqdn() / mangled_src_path / 'sample.log'
    port = 9999
    with ExitStack() as stack:
        agent_cmd = [
            'logline-agent',
            '--scan', 'agent-src/*.log',
            '--server', f'localhost:{port}',
            '--tls',
            '--tls-cert', 'cert.pem',
        ]
        server_cmd = [
            'logline-server',
            '--bind', f'localhost:{port}',
            '--dest', 'server-dst',
            '--tls-cert', 'cert.pem',
            '--tls-key', 'key.pem',
            '--client-token-hash', client_token_hash,
        ]
        server_process = stack.enter_context(Popen(server_cmd, env={**os.environ, 'TLS_KEY_PASSWORD': selfsigned_key_password}))
        stack.callback(terminate_process, server_process)
        sleep(.1)
        agent_process = stack.enter_context(Popen(agent_cmd, env={**os.environ, 'CLIENT_TOKEN': client_token}))
        stack.callback(terminate_process, agent_process)
        t0 = monotime()
        sleep(.1)
        while True:
            logger.debug('Checking after %.2f s...', monotime() - t0)
            assert agent_process.poll() is None
            assert server_process.poll() is None
            check_call(['find', str(tmp_path)], stdout=2)
            if not expected_dst_file.exists():
                logger.debug('Still no file in %s', expected_dst_file)
            else:
                sleep(.1)
                # ^^^ sometimes the file exists, but is still empty, so sleep a little more
                assert expected_dst_file.read_text() == '2021-02-22 Hello world!\n'
                logger.debug('Destination file created! %s', expected_dst_file)
                break
            if monotime() - t0 > 2:
                raise Exception('Deadline exceeded')
            sleep(.2)


def terminate_process(p):
    if p.poll() is None:
        logger.info('Terminating process %s args: %s', p.pid, ' '.join(p.args))
        p.terminate()

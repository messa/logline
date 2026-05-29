import hashlib
from types import SimpleNamespace

from pytest import raises

from logline_server.main import (
    check_client_auth,
    sha1_b64,
    sha1_hex,
    sha256_b64,
    sha256_hex,
    verify_prefix,
)


def test_sha256_helpers():
    assert sha256_b64(b'hello') == 'LPJNul+wow4m6DsqxbninhsWHlwfp0JecwQzYpOLmCQ='
    assert sha256_hex(b'hello') == hashlib.sha256(b'hello').hexdigest()


def test_verify_prefix_uses_sha256():
    data = b'some log prefix'
    assert verify_prefix(data, {'sha256': sha256_b64(data)})
    assert not verify_prefix(data, {'sha256': sha256_b64(b'other')})


def test_verify_prefix_falls_back_to_sha1_for_older_agents():
    data = b'some log prefix'
    assert verify_prefix(data, {'sha1': sha1_b64(data)})
    assert not verify_prefix(data, {'sha1': sha1_b64(b'other')})


def test_verify_prefix_prefers_sha256_when_both_present():
    data = b'some log prefix'
    # SHA-256 matches but SHA-1 does not -> still a match (SHA-256 wins).
    assert verify_prefix(data, {'sha256': sha256_b64(data), 'sha1': sha1_b64(b'other')})


def test_verify_prefix_without_hash_is_rejected():
    assert not verify_prefix(b'data', {})


def test_check_client_auth_accepts_sha256_hash():
    token = 'topsecret'
    conf = SimpleNamespace(client_token_hashes={sha256_hex(token.encode('utf-8'))})
    check_client_auth(conf, {'client_token': token})


def test_check_client_auth_accepts_legacy_sha1_hash():
    token = 'topsecret'
    conf = SimpleNamespace(client_token_hashes={sha1_hex(token.encode('utf-8'))})
    check_client_auth(conf, {'client_token': token})


def test_check_client_auth_rejects_unknown_token():
    conf = SimpleNamespace(client_token_hashes={sha256_hex(b'topsecret')})
    with raises(Exception):
        check_client_auth(conf, {'client_token': 'wrong'})

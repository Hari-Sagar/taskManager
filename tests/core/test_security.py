from datetime import timedelta

import jwt
import pytest

from habit_tracker.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrips_and_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_access_token_roundtrips():
    token = create_access_token(subject="42")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"


def test_access_token_rejects_tampered_token():
    token = create_access_token(subject="42")
    # Flip a character well inside the header segment, not the last
    # character of the whole token: base64's final (partial) group can
    # have "don't care" padding bits where some alternate characters
    # decode to the identical bytes, so tampering the very last character
    # can non-deterministically fail to actually change anything.
    tampered = token[:10] + ("a" if token[10] != "a" else "b") + token[11:]
    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)


def test_access_token_rejects_expired_token():
    token = create_access_token(subject="42", expires_delta=timedelta(seconds=-1))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_refresh_token_is_random_and_hash_is_deterministic():
    raw_a, hash_a = generate_refresh_token()
    raw_b, hash_b = generate_refresh_token()

    assert raw_a != raw_b
    assert hash_a != hash_b
    assert hash_refresh_token(raw_a) == hash_a

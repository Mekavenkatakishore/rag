"""
test_security.py
────────────────
Unit tests for core cryptographic functions:
- Salt generation uniqueness
- PBKDF2 password hashing & verification
- JWT access token creation, payload verification, and tamper detection
"""

import jwt
import pytest
from app.core.security import (
    generate_salt,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    SECRET_KEY,
    ALGORITHM,
)

def test_generate_salt_uniqueness():
    """Verify salts are 64 hex characters and cryptographically distinct."""
    salt1 = generate_salt()
    salt2 = generate_salt()
    assert len(salt1) == 64
    assert len(salt2) == 64
    assert salt1 != salt2

def test_password_hashing_and_verification():
    """Verify passwords hash deterministically with salt and verify correctly."""
    password = "SuperSecurePassword123!"
    salt = generate_salt()
    
    hashed = hash_password(password, salt)
    assert isinstance(hashed, str)
    assert len(hashed) == 64  # SHA-256 hex output is 64 characters
    
    # Correct password must verify True
    assert verify_password(password, hashed, salt) is True
    
    # Wrong password must verify False
    assert verify_password("WrongPassword!", hashed, salt) is False

def test_jwt_create_and_decode_valid():
    """Verify JWT access tokens encode user claims and decode accurately."""
    user_id = 42
    username = "hr_manager"
    
    token = create_access_token(user_id=user_id, username=username)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # Header.Payload.Signature
    
    payload = decode_access_token(token)
    assert payload["user_id"] == user_id
    assert payload["username"] == username
    assert "exp" in payload

def test_jwt_tampered_token_rejected():
    """Verify altered JWT signatures raise InvalidTokenError."""
    token = create_access_token(user_id=1, username="admin")
    
    # Tamper with the token string
    tampered_token = token[:-4] + "abcd"
    
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered_token)


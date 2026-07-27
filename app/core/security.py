"""
security.py
───────────
Handles two security concerns:

1. PASSWORD HASHING using Python built-in hashlib.pbkdf2_hmac
   - Never stores plain-text passwords
   - Uses a unique random salt per user to prevent rainbow table attacks
   - PBKDF2 is an industry-standard key derivation function

2. JWT TOKEN generation and verification using the PyJWT library
   - Tokens are signed with HS256 algorithm using a secret key from .env
   - Tokens carry a user_id payload and an expiry timestamp (exp)
   - Any tampering with the token payload makes the signature invalid
"""

import os
import hashlib
import hmac
import secrets
import datetime
import jwt  # pip install pyjwt
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "rag_pro_dev_secret_change_in_production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


# ─── Password Hashing ─────────────────────────────────────────────────────────

def generate_salt() -> str:
    """
    Generates a cryptographically random 32-byte salt.
    Stored alongside the hashed password in the database.
    
    Why? Two users with the same password will have different hashes,
    so attackers cannot use precomputed rainbow tables.
    """
    return secrets.token_hex(32)  # 64 hex characters


def hash_password(password: str, salt: str) -> str:
    """
    Hashes a plain-text password using PBKDF2-HMAC-SHA256.

    Args:
        password: The raw password string provided by the user.
        salt: The unique random salt generated for this user.

    Returns:
        A hex-encoded string of the hashed password.

    How it works:
        PBKDF2 applies SHA-256 hundreds of thousands of times (iterations),
        making brute-force attacks computationally expensive.
    """
    key = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        iterations=260_000  # NIST recommended minimum
    )
    return key.hex()


def verify_password(plain_password: str, hashed_password: str, salt: str) -> bool:
    """
    Verifies a user-provided password against the stored hash.

    Recomputes the hash with the same salt and compares using
    hmac.compare_digest to prevent timing-based attacks.

    Returns:
        True if password matches, False otherwise.
    """
    recomputed_hash = hash_password(plain_password, salt)
    return hmac.compare_digest(recomputed_hash, hashed_password)


# ─── JWT Token ────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str) -> str:
    """
    Creates a signed JWT access token.

    Payload contains:
        - user_id: Primary key from the users table.
        - username: For display purposes.
        - exp: Expiry timestamp (UTC now + TOKEN_EXPIRE_HOURS).

    Returns:
        A compact JWT string: "header.payload.signature"
    """
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": expire
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token signature is invalid or tampered.

    Returns:
        The decoded payload dict containing user_id and username.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload

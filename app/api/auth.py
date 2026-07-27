"""
auth.py
───────
Authentication API routes:

    POST /auth/register  → Create a new user account
    POST /auth/login     → Authenticate credentials, receive JWT token
    GET  /auth/me        → Get the currently logged-in user's profile (protected)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, field_validator

from app.db import user_db
from app.core.security import generate_salt, hash_password, verify_password, create_access_token
from app.api.deps import get_current_user
from app.utils.logger import logger

auth_router = APIRouter()


# ─── Request / Response Schemas ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(v) > 32:
            raise ValueError("Username must be at most 32 characters.")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters.")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


# ─── Routes ───────────────────────────────────────────────────────────────────

@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    """
    Register a new user.

    Steps:
        1. Validate input fields (username length, password length).
        2. Generate a unique random salt.
        3. Hash the password with PBKDF2-HMAC using the salt.
        4. Store hashed password + salt in the SQLite DB (never the plain password).
        5. Return a success message.
    """
    logger.info(f"Registration attempt: username='{request.username}', email='{request.email}'")

    # Generate salt and hash the password
    salt = generate_salt()
    hashed_pw = hash_password(request.password, salt)

    try:
        user = user_db.create_user(
            username=request.username,
            email=request.email,
            hashed_password=hashed_pw,
            salt=salt
        )
    except ValueError as e:
        logger.warning(f"Registration rejected: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logger.info(f"User registered successfully: id={user['id']}, username='{user['username']}'")
    return {
        "status": "success",
        "message": f"Account created successfully! Welcome, {user['username']}.",
        "user_id": user["id"]
    }


@auth_router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """
    Authenticate a user and issue a JWT access token.

    Steps:
        1. Fetch user record from SQLite DB by username.
        2. Retrieve the stored salt and recompute the hash.
        3. Compare recomputed hash with stored hash (constant-time).
        4. If match: create and return a signed JWT token.
        5. If no match: return 401 Unauthorized.
    """
    logger.info(f"Login attempt: username='{request.username}'")

    # Fetch user from DB
    user = user_db.get_user_by_username(request.username)
    if user is None:
        logger.warning(f"Login failed: user '{request.username}' not found.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    # Verify the password
    if not verify_password(request.password, user["hashed_password"], user["salt"]):
        logger.warning(f"Login failed: wrong password for user '{request.username}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    # Issue the JWT token
    token = create_access_token(user_id=user["id"], username=user["username"])
    logger.info(f"Login successful: username='{user['username']}', id={user['id']}")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        username=user["username"]
    )


@auth_router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """
    Returns the currently authenticated user's profile info.
    Requires a valid Bearer token in the Authorization header.
    """
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "email": current_user["email"],
        "created_at": current_user["created_at"]
    }

"""
deps.py
───────
FastAPI Dependency: get_current_user

This is the "guard at the door" for protected endpoints.
Any route that declares `current_user = Depends(get_current_user)`
will automatically:
  1. Extract the JWT token from the Authorization: Bearer <token> header.
  2. Decode and verify the token's signature and expiry.
  3. Fetch the matching user from the SQLite database.
  4. Inject the user dict into the route function, or raise 401 if invalid.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.db.user_db import get_user_by_id

# HTTPBearer tells FastAPI to expect "Authorization: Bearer <token>" headers
# auto_error=False lets us return a custom 401 message
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    FastAPI dependency that validates the JWT Bearer token from the request header.

    Flow:
        Request arrives → Extract Bearer token → Decode JWT → Fetch user from DB
        → Return user dict (injected into the route) or raise 401 Unauthorized

    Usage in any protected endpoint:
        @router.post("/upload")
        async def upload(current_user: dict = Depends(get_current_user)):
            ...
    """
    # 1. Check that the Authorization header was actually provided
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in to access this resource.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    # 2. Decode and verify the JWT token
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 3. Verify the user still exists in the database
    user_id = payload.get("user_id")
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 4. Return the user dict — injected into the route function
    return user

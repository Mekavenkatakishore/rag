"""
auth.py
───────
Authentication API router. Thin controller calling auth_service.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.auth_schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services.auth import register_user, authenticate_user
from app.api.deps import get_current_user
from app.core.exceptions import AuthenticationError
from app.utils.logger import logger

auth_router = APIRouter()

@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    """Registers a new user account."""
    logger.info(f"Registration attempt for username: '{request.username}'")
    try:
        user = register_user(request.username, request.email, request.password)
        return {
            "status": "success",
            "message": f"Account created successfully! Welcome, {user['username']}.",
            "user_id": user["id"]
        }
    except ValueError as e:
        logger.warning(f"Registration rejected: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@auth_router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """Authenticates user credentials and issues JWT token."""
    logger.info(f"Login attempt for username: '{request.username}'")
    try:
        return authenticate_user(request.username, request.password)
    except AuthenticationError as ae:
        logger.warning(f"Login failed for username '{request.username}': {ae.message}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ae.message)
    except Exception as e:
        logger.error(f"Unexpected login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@auth_router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    """Returns profile for currently authenticated user."""
    return current_user

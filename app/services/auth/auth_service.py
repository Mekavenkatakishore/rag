from app.core.security import (
    generate_salt,
    hash_password,
    verify_password,
    create_access_token,
)
from app.core.exceptions import AuthenticationError
from app.db import user_db

def register_user(username: str, email: str, password: str) -> dict:
    """Business logic for user registration."""
    salt = generate_salt()
    hashed_password = hash_password(password, salt)
    return user_db.create_user(username=username, email=email, hashed_password=hashed_password, salt=salt)

def authenticate_user(username: str, password: str) -> dict:
    """Business logic for user authentication."""
    user = user_db.get_user_by_username(username)
    if not user:
        raise AuthenticationError("Invalid username or password")
        
    if not verify_password(password, user["hashed_password"], user["salt"]):
        raise AuthenticationError("Invalid username or password")
        
    token = create_access_token(user_id=user["id"], username=user["username"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"]
    }

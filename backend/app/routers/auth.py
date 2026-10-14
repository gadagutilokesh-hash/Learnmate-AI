import re
from fastapi import APIRouter, HTTPException, Depends, Response, status
from app.models.schema import UserRegisterRequest, UserLoginRequest, UserResponse, AuthTokenResponse
from app.core.auth import hash_password, verify_password, create_access_token, get_current_user
from app.core.config import settings
from app.db.storage import storage

router = APIRouter(prefix="/auth", tags=["Authentication"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="learnmate_session",
        value=token,
        max_age=settings.SESSION_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE or (settings.ENVIRONMENT.lower() == "production"),
        path="/"
    )

@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, response: Response):
    clean_email = req.email.lower().strip()
    if not clean_email or not EMAIL_REGEX.match(clean_email):
        raise HTTPException(status_code=400, detail="A valid email address is required")
    
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    existing = storage.get_user_by_email(clean_email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email address already exists")

    pwd_hash = hash_password(req.password)
    user = storage.create_user(
        email=clean_email,
        password_hash=pwd_hash,
        full_name=req.full_name.strip() if req.full_name else None,
        role="user"
    )

    token = create_access_token(user_id=user["id"], email=user["email"], role=user["role"])
    _set_auth_cookie(response, token)

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            role=user["role"],
            created_at=user["created_at"]
        )
    )

@router.post("/login", response_model=AuthTokenResponse)
def login(req: UserLoginRequest, response: Response):
    clean_email = req.email.lower().strip()
    user = storage.get_user_by_email(clean_email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user_id=user["id"], email=user["email"], role=user["role"])
    _set_auth_cookie(response, token)

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            role=user["role"],
            created_at=user["created_at"]
        )
    )

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="learnmate_session",
        path="/"
    )
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user.get("full_name"),
        role=current_user["role"],
        created_at=current_user["created_at"]
    )

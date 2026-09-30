import time
from collections import defaultdict, deque
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, get_current_user
from app.models.user import User
from app.schemas.auth import Token, UserResponse, LoginRequest, ChangePasswordRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Simple in-memory brute-force guard: max failed attempts per client+username in a sliding window.
_MAX_FAILURES = 8
_WINDOW_SECONDS = 15 * 60
_failures: dict[str, deque] = defaultdict(deque)


def _client_key(request: Request, username: str) -> str:
    # Behind Cloudflare Tunnel every request comes from localhost; the real IP is in this header.
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")
    return f"{ip}:{username.lower()}"


def _check_rate_limit(key: str) -> None:
    attempts = _failures[key]
    now = time.monotonic()
    while attempts and now - attempts[0] > _WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= _MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )


def _authenticate(request: Request, username: str, password: str, db: Session) -> Token:
    username = username.strip()
    key = _client_key(request, username)
    _check_rate_limit(key)

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        _failures[key].append(time.monotonic())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")

    _failures.pop(key, None)
    access_token = create_access_token(
        subject=user.username,
        role=user.role,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 compatible token login, returning access token."""
    return _authenticate(request, form_data.username, form_data.password, db)


@router.post("/login/json", response_model=Token)
def login_json(
    request: Request,
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """JSON body login endpoint for mobile clients."""
    return _authenticate(request, credentials.username, credentials.password, db)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve profile of authenticated user."""
    return current_user


@router.get("/discovery")
def get_discovery(current_user: User = Depends(get_current_user)):
    """Where (and with which key) the server publishes its current address, so the app can follow URL changes.
    Only signed-in users get the key, so nobody else can point the app at a different server."""
    return {"server": settings.DISCOVERY_SERVER, "topic": settings.DISCOVERY_TOPIC, "key": settings.DISCOVERY_KEY}


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Let a signed-in teacher replace their password."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(body.new_password)
    db.commit()

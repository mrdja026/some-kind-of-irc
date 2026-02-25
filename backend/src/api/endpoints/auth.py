# mypy: ignore-errors
# pyright: ignore

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
from urllib.parse import urlencode
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional, Dict, Any, cast
import secrets
import httpx

from src.core.config import settings
from src.core.database import get_db
from src.core.admin import is_user_admin
from src.models.user import User
from src.models.channel import Channel
from src.models.membership import Membership
from src.models.gmail_token import GmailToken
from src.services.gmail_service import fetch_latest_emails
from src.services.irc_logger import log_nick_user
from src.services.event_publisher import publish_user_registered
from src.services.game_service import GameService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Password hashing with bcrypt cost factor 12
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

GUEST_PREFIX = "guest_"
NPC_PREFIX = "npc_"
NPC_SEED_COUNT = 2
GAME_CHANNEL_NAME = "#game"
GUEST_USERNAME = "guest2"

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_STATE_COOKIE = "gmail_oauth_state"
GMAIL_STATE_TTL_SECONDS = 15 * 60

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    status: str
    profile_picture_url: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None


class GmailAuthUrlResponse(BaseModel):
    authorization_url: str


class GmailCallbackResponse(BaseModel):
    status: str


class AuthGameResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    username: str
    channel_id: int
    snapshot: Optional[Dict[str, Any]] = None

# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt only. Returns False if hash is invalid."""
    try:
        # bcrypt hashes start with $2a$, $2b$, or $2y$
        if not hashed_password.startswith('$2'):
            return False
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt with cost factor 12."""
    return pwd_context.hash(password)

def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    """Authenticate user. Rejects legacy users (hash_type is None) - they must reset password."""
    user = get_user(db, username)
    
    if not user:
        return False
    
    # Reject legacy users - force password reset
    if user.hash_type is None:
        return False
    
    if not verify_password(password, str(user.password_hash)):
        return False
        
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def _ensure_gmail_oauth_config() -> None:
    if not settings.GMAIL_OAUTH_CLIENT_ID or not settings.GMAIL_OAUTH_CLIENT_SECRET or not settings.GMAIL_OAUTH_REDIRECT_URL:
        raise HTTPException(status_code=500, detail="Gmail OAuth is not configured")


def _ensure_admin_user(user: User) -> None:
    if not is_user_admin(user.username):
        raise HTTPException(status_code=404, detail="Not Found")


def _build_gmail_auth_url(state: str) -> str:
    scopes = settings.GMAIL_OAUTH_SCOPES or "https://www.googleapis.com/auth/gmail.readonly"
    params = {
        "client_id": settings.GMAIL_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GMAIL_OAUTH_REDIRECT_URL,
        "response_type": "code",
        "scope": scopes,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GMAIL_AUTH_URL}?{urlencode(params)}"


async def _exchange_gmail_code(code: str) -> dict:
    payload = {
        "client_id": settings.GMAIL_OAUTH_CLIENT_ID,
        "client_secret": settings.GMAIL_OAUTH_CLIENT_SECRET,
        "redirect_uri": settings.GMAIL_OAUTH_REDIRECT_URL,
        "grant_type": "authorization_code",
        "code": code,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(GMAIL_TOKEN_URL, data=payload)
    if response.is_error:
        raise HTTPException(status_code=400, detail="Gmail OAuth token exchange failed")
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Gmail token response") from exc


def _generate_unique_username(db: Session, prefix: str) -> str:
    while True:
        suffix = secrets.token_hex(4)
        username = f"{prefix}{suffix}"
        if get_user(db, username) is None:
            return username


def _create_guest_user(db: Session, prefix: str) -> User:
    username = _generate_unique_username(db, prefix)
    password = secrets.token_urlsafe(12)
    hashed_password = get_password_hash(password)
    user = User(username=username, password_hash=hashed_password, hash_type="bcrypt")
    db.add(user)
    db.commit()
    db.refresh(user)
    log_nick_user(user.id, user.username)
    return user


def _get_or_create_fixed_user(db: Session, username: str) -> User:
    user = get_user(db, username)
    if user:
        return user
    password = secrets.token_urlsafe(12)
    hashed_password = get_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password, hash_type="bcrypt")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    log_nick_user(new_user.id, new_user.username)
    return new_user


def _get_or_create_game_channel(db: Session) -> Channel:
    channel = db.query(Channel).filter(Channel.name == GAME_CHANNEL_NAME).first()
    if channel:
        return channel
    channel = Channel(name=GAME_CHANNEL_NAME, type="public", is_data_processor=False)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def _ensure_membership(db: Session, user_id: int, channel_id: int) -> None:
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.channel_id == channel_id,
    ).first()
    if membership:
        return
    db.add(Membership(user_id=user_id, channel_id=channel_id))
    db.commit()


def _ensure_npc_sessions(db: Session, game_service: GameService, channel_id: int) -> None:
    states = game_service.get_all_game_states_in_channel(channel_id)
    npc_count = 0
    for state in states:
        if bool(state.get("is_npc", False)):
            npc_count += 1
    to_create = max(0, NPC_SEED_COUNT - npc_count)
    for _ in range(to_create):
        npc_user = _create_guest_user(db, NPC_PREFIX)
        npc_user_id = cast(int, npc_user.id)
        _ensure_membership(db, npc_user_id, channel_id)
        game_service.bootstrap_small_arena_join(npc_user_id, channel_id)

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Get token from cookie
        token = request.cookies.get("access_token")
        if not token:
            raise credentials_exception
        
        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
            
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username_value = payload.get("sub")
        if not isinstance(username_value, str):
            raise credentials_exception
        token_data = TokenData(username=username_value)
    except JWTError:
        raise credentials_exception
    username_value = token_data.username
    if username_value is None:
        raise credentials_exception
    user = get_user(db, username=cast(str, username_value))
    if user is None:
        raise credentials_exception
    return user

# API endpoints
@router.post("/register")
async def register(response: Response, user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, password_hash=hashed_password, hash_type="bcrypt")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Publish event for Channel Service to auto-join to #general
    new_user_id = cast(int, new_user.id)
    new_user_username = cast(str, new_user.username)
    publish_user_registered(new_user_id, new_user_username)
    
    # Create and set JWT cookie
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user_username}, expires_delta=access_token_expires
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=int(access_token_expires.total_seconds()),
    )
    log_nick_user(new_user_id, new_user_username)
    return {"message": "Registration successful"}

@router.post("/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user(db, form_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if legacy user (needs password reset)
    if user.hash_type is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password reset required. Please use password reset to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(form_data.password, str(user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    user_username = cast(str, user.username)
    access_token = create_access_token(
        data={"sub": user_username}, expires_delta=access_token_expires
    )
    # Set JWT as HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=int(access_token_expires.total_seconds()),
    )
    log_nick_user(cast(int, user.id), user_username)
    return {"message": "Login successful"}


@router.get("/gmail/start", response_model=GmailAuthUrlResponse)
async def gmail_oauth_start(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    _ensure_gmail_oauth_config()
    _ensure_admin_user(current_user)
    state = secrets.token_urlsafe(16)
    auth_url = _build_gmail_auth_url(state)
    response.set_cookie(
        key=GMAIL_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=GMAIL_STATE_TTL_SECONDS,
    )
    return GmailAuthUrlResponse(authorization_url=auth_url)


@router.get("/callback")
async def gmail_oauth_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_gmail_oauth_config()
    _ensure_admin_user(current_user)
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    expected_state = request.cookies.get(GMAIL_STATE_COOKIE)
    if not expected_state or not state or expected_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token_payload = await _exchange_gmail_code(code)
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token")
    token_type = token_payload.get("token_type")
    scope = token_payload.get("scope")
    expires_in = token_payload.get("expires_in")

    if not access_token:
        raise HTTPException(status_code=400, detail="Missing access token")

    expires_at = None
    if expires_in is not None:
        try:
            expires_at = datetime.now() + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None

    user_id = cast(int, current_user.id)
    existing_token = db.query(GmailToken).filter(GmailToken.user_id == user_id).first()
    if existing_token:
        if refresh_token:
            existing_token.refresh_token = refresh_token
        if not existing_token.refresh_token:
            raise HTTPException(status_code=400, detail="Missing refresh token")
        existing_token.access_token = access_token
        existing_token.token_type = token_type
        existing_token.scope = scope
        existing_token.expires_at = expires_at
    else:
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Missing refresh token")
        db.add(
            GmailToken(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_type,
                scope=scope,
                expires_at=expires_at,
            )
        )

    db.commit()
    redirect_url = f"{settings.FRONTEND_URL}/chat"
    redirect_response = RedirectResponse(url=redirect_url, status_code=303)
    redirect_response.delete_cookie(GMAIL_STATE_COOKIE)
    return redirect_response


@router.get("/gmail/messages")
async def get_gmail_messages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_admin_user(current_user)
    try:
        user_id = cast(int, current_user.id)
        emails = await fetch_latest_emails(db, user_id)
        return {"emails": emails}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to fetch Gmail messages")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/auth_game", response_model=AuthGameResponse)
async def auth_game(response: Response, db: Session = Depends(get_db)):
    channel = _get_or_create_game_channel(db)
    guest_user = _get_or_create_fixed_user(db, GUEST_USERNAME)
    guest_user_id = cast(int, guest_user.id)
    channel_id = cast(int, channel.id)
    _ensure_membership(db, guest_user_id, channel_id)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": guest_user.username}, expires_delta=access_token_expires
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=int(access_token_expires.total_seconds()),
    )

    return AuthGameResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=guest_user_id,
        username=cast(str, guest_user.username),
        channel_id=channel_id,
        snapshot=None,
    )

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    profile_picture_url: Optional[str] = None

@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if display_name is being changed
    display_name_value = cast(Optional[str], current_user.display_name)
    username_value = cast(str, current_user.username)
    if display_name_value is not None and display_name_value != "":
        current_display_name = display_name_value
    else:
        current_display_name = username_value
    if user_update.display_name is not None and user_update.display_name != current_display_name:
        # Validate display_name format
        if not user_update.display_name.strip():
            raise HTTPException(status_code=400, detail="Display name cannot be empty")
        if len(user_update.display_name) > 50:
            raise HTTPException(status_code=400, detail="Display name must be 50 characters or less")

        # Check uniqueness (case-insensitive)
        existing_user = db.query(User).filter(
            User.display_name.ilike(user_update.display_name.strip()),
            User.id != current_user.id
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Display name already taken")

        current_user_any = cast(Any, current_user)
        setattr(current_user_any, "display_name", user_update.display_name.strip())
        setattr(current_user_any, "display_name_updated_at", datetime.now())

    # Update profile picture URL if provided
    if user_update.profile_picture_url is not None:
        current_user_any = cast(Any, current_user)
        setattr(current_user_any, "profile_picture_url", user_update.profile_picture_url)

    # Update timestamp
    current_user_any = cast(Any, current_user)
    setattr(current_user_any, "updated_at", datetime.now())

    db.commit()
    db.refresh(current_user)

    # Convert updated_at to ISO string for response
    updated_at_value = cast(Optional[datetime], current_user.updated_at)
    user_dict = {
        "id": cast(int, current_user.id),
        "username": cast(str, current_user.username),
        "display_name": cast(Optional[str], current_user.display_name),
        "status": cast(str, current_user.status),
        "profile_picture_url": cast(Optional[str], current_user.profile_picture_url),
        "updated_at": updated_at_value.isoformat() if updated_at_value is not None else None,
    }

    return user_dict

@router.get("/users/search")
async def search_users(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20
):
    if not username or len(username.strip()) < 1:
        return []
    
    # Search for users by username or display_name (case-insensitive, partial match)
    # Exclude current user
    search_term = username.strip()
    current_user_id = cast(Any, current_user).id
    users = db.query(User).filter(
        (User.username.ilike(f"%{search_term}%")) |
        (User.display_name.isnot(None) & User.display_name.ilike(f"%{search_term}%")),
        User.id != current_user_id
    ).limit(limit).all()
    
    response_users = []
    for user in users:
        updated_at = cast(Optional[datetime], user.updated_at)
        response_users.append({
            "id": cast(Any, user).id,
            "username": str(user.username),
            "display_name": cast(Optional[str], user.display_name),
            "status": str(user.status),
            "profile_picture_url": cast(Optional[str], user.profile_picture_url),
            "updated_at": updated_at.isoformat() if updated_at is not None else None,
        })
    return response_users

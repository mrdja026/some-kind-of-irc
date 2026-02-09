from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional

from src.core.config import settings
from src.core.database import get_db
from src.models.user import User
from src.services.irc_logger import log_nick_user
from src.services.event_publisher import publish_user_registered

router = APIRouter(prefix="/auth", tags=["auth"])

# Password hashing with bcrypt cost factor 12
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

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
    
    if not verify_password(password, user.password_hash):
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
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
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
    publish_user_registered(new_user.id, new_user.username)
    
    # Create and set JWT cookie
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.username}, expires_delta=access_token_expires
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=int(access_token_expires.total_seconds()),
    )
    log_nick_user(new_user.id, new_user.username)
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
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
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
    log_nick_user(user.id, user.username)
    return {"message": "Login successful"}

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
    if user_update.display_name is not None and user_update.display_name != (current_user.display_name or current_user.username):
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

        current_user.display_name = user_update.display_name.strip()
        current_user.display_name_updated_at = datetime.now()

    # Update profile picture URL if provided
    if user_update.profile_picture_url is not None:
        current_user.profile_picture_url = user_update.profile_picture_url

    # Update timestamp
    current_user.updated_at = datetime.now()

    db.commit()
    db.refresh(current_user)

    # Convert updated_at to ISO string for response
    user_dict = {
        "id": current_user.id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "status": current_user.status,
        "profile_picture_url": current_user.profile_picture_url,
        "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
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
    users = db.query(User).filter(
        (User.username.ilike(f"%{search_term}%")) |
        (User.display_name.isnot(None) & User.display_name.ilike(f"%{search_term}%")),
        User.id != current_user.id
    ).limit(limit).all()
    
    return [
        {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "status": user.status,
            "profile_picture_url": user.profile_picture_url,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
        for user in users
    ]

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional
import hashlib

from src.core.config import settings
from src.core.database import get_db
from src.models.user import User
from src.models.channel import Channel
from src.models.membership import Membership
from src.services.irc_logger import log_join, log_nick_user

router = APIRouter(prefix="/auth", tags=["auth"])

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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
def verify_password(plain_password, hashed_password):
    try:
        # Check if this is a SHA-256 hash (64 hex characters)
        if len(hashed_password) == 64 and all(c in '0123456789abcdefABCDEF' for c in hashed_password):
            return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == hashed_password
        else:
            # Otherwise, assume it's a bcrypt hash
            truncated_password = plain_password.encode('utf-8')[:72].decode('utf-8', 'ignore')
            return pwd_context.verify(truncated_password, hashed_password)
    except Exception as e:
        print(f"Password verification failed: {e}")
        return False

def get_password_hash(password):
    # Truncate password to 72 bytes to avoid bcrypt's limit
    # bcrypt has a maximum password length of 72 bytes //find solution that works wittout 72 byte restruiction
    try:
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        return pwd_context.hash(password_bytes)
    except Exception as e:
        # If bcrypt fails for any reason (including password length), use a fallback
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    print(f"Getting user from DB: {username}")
    user = get_user(db, username)
    print(f"User found: {user}")
    
    if not user:
        print("User not found")
        return False
        
    print(f"Verifying password hash: {user.password_hash}")
    password_match = verify_password(password, user.password_hash)
    print(f"Password match: {password_match}")
    
    if not password_match:
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
    new_user = User(username=user.username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Check if general channel exists, create if not
    general_channel = db.query(Channel).filter(Channel.name == "#general").first()
    if not general_channel:
        general_channel = Channel(name="#general", type="public")
        db.add(general_channel)
        db.commit()
        db.refresh(general_channel)
    
    # Add user to general channel
    membership = Membership(user_id=new_user.id, channel_id=general_channel.id)
    db.add(membership)
    db.commit()
    
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
    log_join(new_user.id, general_channel.id, general_channel.name)
    return {"message": "Registration successful"}

@router.post("/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    print(f"Login attempt with username: {form_data.username}")
    try:
        user = authenticate_user(db, form_data.username, form_data.password)
    except Exception as e:
        print(f"Error authenticating user: {e}")
        raise
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if general channel exists, create if not
    general_channel = db.query(Channel).filter(Channel.name == "#general").first()
    if not general_channel:
        general_channel = Channel(name="#general", type="public")
        db.add(general_channel)
        db.commit()
        db.refresh(general_channel)
    
    # Add user to general channel if not already a member
    existing_membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.channel_id == general_channel.id
    ).first()
    if not existing_membership:
        membership = Membership(user_id=user.id, channel_id=general_channel.id)
        db.add(membership)
        db.commit()
    
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
    log_join(user.id, general_channel.id, general_channel.name)
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

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Union
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.responses import RedirectResponse
from jose import JWTError, jwt

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth configuration
config = Config('.env')
oauth = OAuth(config)

# Configure OAuth providers
if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

if settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET:
    oauth.register(
        name='github',
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
        access_token_url='https://github.com/login/oauth/access_token',
        access_token_params=None,
        authorize_url='https://github.com/login/oauth/authorize',
        authorize_params=None,
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'user:email'},
    )

# Token bearer for API access
bearer = HTTPBearer()

# Basic auth for API access
basic = HTTPBasic()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_oauth_id(db: Session, provider: str, oauth_id: str) -> Optional[User]:
    """Get user by OAuth provider and ID"""
    return db.query(User).filter(
        User.oauth_provider == provider,
        User.oauth_id == oauth_id
    ).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user with username/email and password"""
    user = get_user_by_email(db, username) or get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(db: Session, email: str, username: str, password: str, is_admin: bool = False) -> User:
    """Create a new user"""
    hashed_password = get_password_hash(password)
    db_user = User(
        email=email,
        username=username,
        hashed_password=hashed_password,
        is_admin=is_admin
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_oauth_user(db: Session, email: str, username: str, provider: str, oauth_id: str) -> User:
    """Create a new user from OAuth"""
    db_user = User(
        email=email,
        username=username,
        oauth_provider=provider,
        oauth_id=oauth_id,
        hashed_password=""  # OAuth users don't have passwords
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# Dependency to get current user from session
def get_current_user_from_session(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user from session"""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        return None
    
    return user


# Dependency to get current user from JWT token
def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        return None
    
    return user


# Dependency to get current user from session or Basic Auth
def get_current_user_flexible(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(basic),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from session or Basic Auth"""
    # Try session first
    user = get_current_user_from_session(request, db)
    if user:
        return user
    
    # Try Basic Auth if provided
    if credentials:
        user = authenticate_user(db, credentials.username, credentials.password)
        if user:
            return user
    
    return None


# Dependency to require authentication
def require_auth(current_user: Optional[User] = Depends(get_current_user_flexible)) -> User:
    """Require authentication - supports both session and Basic Auth"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )
    return current_user


# Dependency to require admin access
def require_admin(current_user: User = Depends(require_auth)) -> User:
    """Require admin access"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# OAuth login functions
async def google_login(request: Request):
    """Initiate Google OAuth login"""
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)


async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    token = await oauth.google.authorize_access_token(request)
    user_info = await oauth.google.parse_id_token(request, token)
    
    email = user_info.get('email')
    name = user_info.get('name', email.split('@')[0])
    oauth_id = user_info.get('sub')
    
    # Check if user exists
    user = get_user_by_oauth_id(db, 'google', oauth_id)
    if not user:
        # Create new user
        user = create_oauth_user(db, email, name, 'google', oauth_id)
    
    # Set session
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


async def github_login(request: Request):
    """Initiate GitHub OAuth login"""
    redirect_uri = request.url_for('github_callback')
    return await oauth.github.authorize_redirect(request, redirect_uri)


async def github_callback(request: Request, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    token = await oauth.github.authorize_access_token(request)
    resp = await oauth.github.get('user', token=token)
    user_info = resp.json()
    
    email = user_info.get('email')
    name = user_info.get('login', email.split('@')[0])
    oauth_id = str(user_info.get('id'))
    
    # Check if user exists
    user = get_user_by_oauth_id(db, 'github', oauth_id)
    if not user:
        # Create new user
        user = create_oauth_user(db, email, name, 'github', oauth_id)
    
    # Set session
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


def logout(request: Request):
    """Logout user by clearing session"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


def init_test_user(db: Session):
    """Initialize test user for development"""
    # Check if test user already exists
    test_user = get_user_by_email(db, "admin@example.com")
    if not test_user:
        create_user(
            db=db,
            email="admin@example.com",
            username="admin",
            password="password123",
            is_admin=True
        )
        print("✅ Test user created: admin@example.com / password123")
    else:
        print("✅ Test user already exists") 
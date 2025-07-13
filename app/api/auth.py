from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.security import (
    authenticate_user, create_user, init_test_user,
    google_login, google_callback, github_login, github_callback, logout,
    get_current_user_from_session
)
from app.db.database import get_db
from app.db.models import User

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page with OAuth and username/password options"""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Login with username/email and password"""
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Set session
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)

@router.get("/auth/google")
async def google_auth(request: Request):
    """Initiate Google OAuth login"""
    return await google_login(request)

@router.get("/auth/google/callback")
async def google_auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    return await google_callback(request, db)

@router.get("/auth/github")
async def github_auth(request: Request):
    """Initiate GitHub OAuth login"""
    return await github_login(request)

@router.get("/auth/github/callback")
async def github_auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    return await github_callback(request, db)

@router.get("/logout")
async def logout_route(request: Request):
    """Logout user"""
    return logout(request) 
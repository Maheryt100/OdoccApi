# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

from database import get_db
import auth
import schemas

router = APIRouter()

@router.post("/login", response_model=schemas.TokenResponse)
async def login_topo_user(
    credentials: schemas.TopoUserLogin,
    db: Session = Depends(get_db)
):
    """Connexion utilisateur TopoManager"""
    user = db.execute(text("""
        SELECT id, username, email, full_name, password_hash, role, is_active, allowed_districts
        FROM topo_users
        WHERE username = :username
    """), {"username": credentials.username}).first()
    
    if not user:
        raise HTTPException(401, "Identifiants incorrects")
    
    if not user.is_active:
        raise HTTPException(403, "Compte désactivé")
    
    if not auth.verify_password(credentials.password, user.password_hash):
        raise HTTPException(401, "Identifiants incorrects")
    
    token_data = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role
    }
    
    access_token = auth.create_access_token(token_data)
    
    db.execute(text("""
        UPDATE topo_users 
        SET last_token_refresh = NOW()
        WHERE id = :id
    """), {"id": user.id})
    db.commit()
    
    allowed_districts = None
    if user.allowed_districts:
        try:
            allowed_districts = json.loads(user.allowed_districts)
        except:
            allowed_districts = []
    
    return schemas.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=3600,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "allowed_districts": allowed_districts
        }
    )
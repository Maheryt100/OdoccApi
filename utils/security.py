# utils/security.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
import logging
import os

from database import get_db
import auth

logger = logging.getLogger(__name__)

GEODOC_SECRET = os.getenv("GEODOC_SECRET_KEY")

# Configuration du système de sécurité Bearer Token
security = HTTPBearer(
    scheme_name="Bearer Token",
    description="Entrez votre token JWT",
    auto_error=False
)

async def verify_api_key_or_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> dict:
    """Authentification flexible (TopoManager ou GeODOC)"""
    if not credentials:
        raise HTTPException(401, "Token Bearer requis")
    
    token = credentials.credentials
    
    # Essayer TopoManager
    try:
        payload = auth.verify_token(token)
        if payload:
            user = db.execute(text("""
                SELECT id, username, email, full_name, role, allowed_districts
                FROM topo_users
                WHERE username = :username AND is_active = true
            """), {"username": payload}).first()
            
            if user:
                allowed_districts = None
                if user.allowed_districts:
                    try:
                        allowed_districts = json.loads(user.allowed_districts)
                    except:
                        allowed_districts = []
                
                return {
                    "source": "topomanager",
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                    "allowed_districts": allowed_districts
                }
    except Exception as e:
        logger.debug(f"TopoManager auth failed: {e}")
    
    # Essayer GeODOC
    try:
        payload = auth.verify_token(token, GEODOC_SECRET)
        if payload:
            user = db.execute(text("""
                SELECT id, name, email, role, id_district
                FROM users
                WHERE email = :email AND status = true
            """), {"email": payload}).first()
            
            if user:
                return {
                    "source": "geodoc",
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "role": user.role,
                    "id_district": user.id_district
                }
    except Exception as e:
        logger.debug(f"GeODOC auth failed: {e}")
    
    raise HTTPException(401, "Token invalide")
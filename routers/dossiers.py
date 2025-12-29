# routers/dossiers.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from database import get_db
from utils.security import verify_api_key_or_jwt
import schemas

router = APIRouter()

@router.get("/search", response_model=List[schemas.DossierSearchResult])
async def search_dossiers(
    q: str = Query(..., min_length=1, max_length=100),
    district_id: Optional[int] = Query(None),
    include_closed: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(verify_api_key_or_jwt),
    db: Session = Depends(get_db)
):
    """Recherche de dossiers GeODOC"""
    
    # Vérification des permissions
    if current_user["source"] == "topomanager":
        allowed = current_user.get("allowed_districts")
        if allowed and district_id and district_id not in allowed:
            raise HTTPException(403, f"Accès refusé au district {district_id}")
    
    elif current_user["source"] == "geodoc":
        if current_user["role"] not in ["super_admin", "central_user"]:
            if district_id and district_id != current_user.get("id_district"):
                raise HTTPException(403, "Accès refusé à ce district")
            district_id = current_user.get("id_district")
    
    # Construction de la requête
    query_str = """
        SELECT 
            d.id, d.nom_dossier, d.numero_ouverture, d.commune, d.fokontany,
            d.id_district, dist.nom_district, d.date_fermeture,
            COUNT(DISTINCT p.id) as proprietes_count,
            COUNT(DISTINCT c.id_demandeur) as demandeurs_count
        FROM dossiers d
        JOIN districts dist ON d.id_district = dist.id
        LEFT JOIN proprietes p ON p.id_dossier = d.id
        LEFT JOIN contenir c ON c.id_dossier = d.id
        WHERE (
            CAST(d.numero_ouverture AS TEXT) = :q
            OR LOWER(d.nom_dossier) LIKE LOWER(:q_like)
            OR LOWER(d.commune) LIKE LOWER(:q_like)
        )
    """
    
    params = {"q": q, "q_like": f"%{q}%"}
    
    if district_id:
        query_str += " AND d.id_district = :district_id"
        params["district_id"] = district_id
    
    if not include_closed:
        query_str += " AND d.date_fermeture IS NULL"
    
    query_str += """
        GROUP BY d.id, d.nom_dossier, d.numero_ouverture, d.commune, 
                 d.fokontany, d.id_district, dist.nom_district, d.date_fermeture
        ORDER BY 
            CASE WHEN CAST(d.numero_ouverture AS TEXT) = :q THEN 0 ELSE 1 END,
            d.numero_ouverture DESC
        LIMIT :limit
    """
    
    params["limit"] = limit
    results = db.execute(text(query_str), params).fetchall()
    
    return [
        schemas.DossierSearchResult(
            id=r.id,
            nom_dossier=r.nom_dossier,
            numero_ouverture=r.numero_ouverture,
            commune=r.commune,
            fokontany=r.fokontany,
            district_id=r.id_district,
            district_nom=r.nom_district,
            is_closed=r.date_fermeture is not None,
            proprietes_count=r.proprietes_count or 0,
            demandeurs_count=r.demandeurs_count or 0
        )
        for r in results
    ]
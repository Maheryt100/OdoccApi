# routers/staging.py
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import json
import os
import logging

from database import get_db
from utils.security import verify_api_key_or_jwt
import schemas

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[schemas.StagingItemResponse])
async def get_staging_imports(
    status: Optional[str] = Query("pending"),
    entity_type: Optional[str] = Query(None),
    district_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(verify_api_key_or_jwt),
    db: Session = Depends(get_db)
):
    """Liste des imports en attente"""
    
    if current_user["source"] == "geodoc":
        if current_user["role"] not in ["super_admin", "central_user"]:
            if district_id and district_id != current_user["id_district"]:
                raise HTTPException(403, "Accès refusé")
            district_id = current_user["id_district"]
    
    query = """
        SELECT 
            ti.*, d.nom_dossier, d.numero_ouverture as dossier_numero_ouverture,
            dist.nom_district
        FROM topo_imports ti
        JOIN dossiers d ON ti.target_dossier_id = d.id
        JOIN districts dist ON ti.target_district_id = dist.id
        WHERE 1=1
    """
    params = {}
    
    if status:
        query += " AND ti.status = :status"
        params["status"] = status
    
    if entity_type:
        query += " AND ti.entity_type = :entity_type"
        params["entity_type"] = entity_type
    
    if district_id:
        query += " AND ti.target_district_id = :district"
        params["district"] = district_id
    
    query += " ORDER BY ti.import_date DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
    
    imports = db.execute(text(query), params).fetchall()
    
    results = []
    for imp in imports:
        files = db.execute(text("""
            SELECT original_name, file_size, file_extension, category, mime_type
            FROM topo_files
            WHERE import_id = :import_id
            ORDER BY category, original_name
        """), {"import_id": imp.id}).fetchall()
        
        try:
            raw_data = json.loads(imp.raw_data) if isinstance(imp.raw_data, str) else imp.raw_data
        except:
            raw_data = {}
        
        try:
            warnings = json.loads(imp.warnings) if imp.warnings else None
        except:
            warnings = None
        
        matched_entity_details = None
        if imp.matched_entity_id:
            if imp.entity_type == 'propriete':
                entity = db.execute(text("""
                    SELECT id, lot, titre, proprietaire, contenance, nature, vocation
                    FROM proprietes WHERE id = :id
                """), {"id": imp.matched_entity_id}).first()
                
                if entity:
                    matched_entity_details = {
                        "id": entity.id,
                        "lot": entity.lot,
                        "titre": entity.titre,
                        "proprietaire": entity.proprietaire,
                        "contenance": entity.contenance,
                        "nature": entity.nature,
                        "vocation": entity.vocation
                    }
            elif imp.entity_type == 'demandeur':
                entity = db.execute(text("""
                    SELECT id, cin, nom_demandeur, prenom_demandeur, 
                           date_naissance, titre_demandeur
                    FROM demandeurs WHERE id = :id
                """), {"id": imp.matched_entity_id}).first()
                
                if entity:
                    matched_entity_details = {
                        "id": entity.id,
                        "cin": entity.cin,
                        "nom_demandeur": entity.nom_demandeur,
                        "prenom_demandeur": entity.prenom_demandeur,
                        "date_naissance": entity.date_naissance.isoformat() if entity.date_naissance else None,
                        "titre_demandeur": entity.titre_demandeur
                    }
        
        results.append(schemas.StagingItemResponse(
            id=imp.id,
            batch_id=imp.batch_id,
            entity_type=imp.entity_type,
            action_suggested=imp.action_suggested,
            dossier_id=imp.target_dossier_id,
            dossier_nom=imp.nom_dossier,
            dossier_numero_ouverture=imp.dossier_numero_ouverture,
            district_id=imp.target_district_id,
            district_nom=imp.nom_district,
            raw_data=raw_data,
            matched_entity_id=imp.matched_entity_id,
            matched_entity_details=matched_entity_details,
            match_confidence=float(imp.match_confidence) if imp.match_confidence else None,
            match_method=imp.match_method,
            has_warnings=imp.has_warnings,
            warnings=warnings,
            files_count=len(files),
            files=[
                {
                    "name": f.original_name,
                    "size": f.file_size,
                    "extension": f.file_extension,
                    "category": f.category,
                    "mime_type": f.mime_type
                }
                for f in files
            ],
            topo_user_name=imp.topo_user_name,
            import_date=imp.import_date,
            status=imp.status,
            processed_at=imp.processed_at,
            rejection_reason=imp.rejection_reason
        ))
    
    return results

@router.get("/{import_id}", response_model=schemas.StagingItemResponse)
async def get_import_details(
    import_id: int,
    current_user: dict = Depends(verify_api_key_or_jwt),
    db: Session = Depends(get_db)
):
    """Détails d'un import"""
    
    imp = db.execute(text("""
        SELECT 
            ti.*, d.nom_dossier, d.numero_ouverture as dossier_numero_ouverture,
            dist.nom_district
        FROM topo_imports ti
        JOIN dossiers d ON ti.target_dossier_id = d.id
        JOIN districts dist ON ti.target_district_id = dist.id
        WHERE ti.id = :id
    """), {"id": import_id}).first()
    
    if not imp:
        raise HTTPException(404, "Import introuvable")
    
    # Permissions
    if current_user["source"] == "geodoc":
        if current_user["role"] not in ["super_admin", "central_user"]:
            if imp.target_district_id != current_user["id_district"]:
                raise HTTPException(403, "Accès refusé")
    
    # Fichiers
    files = db.execute(text("""
        SELECT original_name, file_size, file_extension, category, storage_path, mime_type
        FROM topo_files
        WHERE import_id = :import_id
    """), {"import_id": import_id}).fetchall()
    
    try:
        raw_data = json.loads(imp.raw_data) if isinstance(imp.raw_data, str) else imp.raw_data
    except:
        raw_data = {}
    
    try:
        warnings = json.loads(imp.warnings) if imp.warnings else None
    except:
        warnings = None
    
    # Matched entity details
    matched_entity_details = None
    if imp.matched_entity_id:
        if imp.entity_type == 'propriete':
            entity = db.execute(text("""
                SELECT id, lot, titre, proprietaire, contenance, nature, vocation, type_operation
                FROM proprietes WHERE id = :id
            """), {"id": imp.matched_entity_id}).first()
            
            if entity:
                matched_entity_details = {
                    "id": entity.id,
                    "lot": entity.lot,
                    "titre": entity.titre,
                    "proprietaire": entity.proprietaire,
                    "contenance": entity.contenance,
                    "nature": entity.nature,
                    "vocation": entity.vocation,
                    "type_operation": entity.type_operation
                }
        elif imp.entity_type == 'demandeur':
            entity = db.execute(text("""
                SELECT id, cin, nom_demandeur, prenom_demandeur, 
                       date_naissance, titre_demandeur, domiciliation, telephone
                FROM demandeurs WHERE id = :id
            """), {"id": imp.matched_entity_id}).first()
            
            if entity:
                matched_entity_details = {
                    "id": entity.id,
                    "cin": entity.cin,
                    "nom_demandeur": entity.nom_demandeur,
                    "prenom_demandeur": entity.prenom_demandeur,
                    "date_naissance": entity.date_naissance.isoformat() if entity.date_naissance else None,
                    "titre_demandeur": entity.titre_demandeur,
                    "domiciliation": entity.domiciliation,
                    "telephone": entity.telephone
                }
    
    return schemas.StagingItemResponse(
        id=imp.id,
        batch_id=imp.batch_id,
        entity_type=imp.entity_type,
        action_suggested=imp.action_suggested,
        dossier_id=imp.target_dossier_id,
        dossier_nom=imp.nom_dossier,
        dossier_numero_ouverture=imp.dossier_numero_ouverture,
        district_id=imp.target_district_id,
        district_nom=imp.nom_district,
        raw_data=raw_data,
        matched_entity_id=imp.matched_entity_id,
        matched_entity_details=matched_entity_details,
        match_confidence=float(imp.match_confidence) if imp.match_confidence else None,
        match_method=imp.match_method,
        has_warnings=imp.has_warnings,
        warnings=warnings,
        files_count=len(files),
        files=[
            {
                "name": f.original_name,
                "size": f.file_size,
                "extension": f.file_extension,
                "category": f.category,
                "path": f.storage_path,
                "mime_type": f.mime_type
            }
            for f in files
        ],
        topo_user_name=imp.topo_user_name,
        import_date=imp.import_date,
        status=imp.status,
        processed_at=imp.processed_at,
        rejection_reason=imp.rejection_reason
    )

@router.put("/{import_id}/validate")
async def validate_import(
    import_id: int,
    request: schemas.ValidateImportRequest,
    current_user: dict = Depends(verify_api_key_or_jwt),
    db: Session = Depends(get_db)
):
    """Valider ou rejeter un import"""
    
    # Vérifier permissions (uniquement GeODOC district users)
    if current_user["source"] != "geodoc":
        raise HTTPException(403, "Seuls les utilisateurs GeODOC peuvent valider")
    
    if current_user["role"] in ["super_admin", "central_user"]:
        raise HTTPException(403, "Les super_admin/central_user ne peuvent pas valider")
    
    # Récupérer import
    imp = db.execute(text("""
        SELECT * FROM topo_imports WHERE id = :id
    """), {"id": import_id}).first()
    
    if not imp:
        raise HTTPException(404, "Import introuvable")
    
    if imp.target_district_id != current_user["id_district"]:
        raise HTTPException(403, "Vous ne pouvez valider que les imports de votre district")
    
    if imp.status != "pending":
        raise HTTPException(400, f"Import déjà traité (statut: {imp.status})")
    
    # Validation
    if request.action == "accept":
        new_status = "validated"
        rejection_reason = None
    else:
        if not request.rejection_reason or len(request.rejection_reason.strip()) < 10:
            raise HTTPException(400, "Motif de rejet requis (min 10 caractères)")
        new_status = "rejected"
        rejection_reason = request.rejection_reason
    
    # Mise à jour
    db.execute(text("""
        UPDATE topo_imports
        SET status = :status, processed_at = NOW(), 
            processed_by = :user_id, rejection_reason = :reason
        WHERE id = :id
    """), {
        "status": new_status,
        "user_id": current_user["id"],
        "reason": rejection_reason,
        "id": import_id
    })
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Import {request.action}é avec succès",
        "import_id": import_id,
        "status": new_status
    }

@router.get("/stats")
async def get_stats(
    current_user: dict = Depends(verify_api_key_or_jwt),
    db: Session = Depends(get_db)
):
    """Statistiques des imports"""
    
    query = "SELECT status, entity_type, target_district_id FROM topo_imports WHERE 1=1"
    params = {}
    
    # Filtre district si nécessaire
    if current_user["source"] == "geodoc":
        if current_user["role"] not in ["super_admin", "central_user"]:
            query += " AND target_district_id = :district"
            params["district"] = current_user["id_district"]
    
    imports = db.execute(text(query), params).fetchall()
    
    total = len(imports)
    pending = sum(1 for i in imports if i.status == 'pending')
    validated = sum(1 for i in imports if i.status == 'validated')
    rejected = sum(1 for i in imports if i.status == 'rejected')
    
    # Par type
    by_entity_type = {}
    for imp in imports:
        by_entity_type[imp.entity_type] = by_entity_type.get(imp.entity_type, 0) + 1
    
    # Par district
    by_district = {}
    for imp in imports:
        by_district[str(imp.target_district_id)] = by_district.get(str(imp.target_district_id), 0) + 1
    
    # Warnings
    warnings_query = "SELECT COUNT(*) FROM topo_imports WHERE has_warnings = true"
    if params.get("district"):
        warnings_query += " AND target_district_id = :district"
    
    with_warnings = db.execute(text(warnings_query), params).scalar()
    
    return schemas.StatsResponse(
        total=total,
        pending=pending,
        validated=validated,
        rejected=rejected,
        with_warnings=with_warnings,
        by_entity_type=by_entity_type,
        by_district=by_district
    )

@router.get("/files/{import_id}/{filename}")
async def download_file(
    import_id: int,
    filename: str,
    current_user: dict = Depends(verify_api_key_or_jwt),
    db: Session = Depends(get_db)
):
    """Télécharger un fichier de staging"""
    
    # Vérifier que le fichier appartient à un import autorisé
    file_record = db.execute(text("""
        SELECT 
            tf.storage_path,
            tf.mime_type,
            ti.target_district_id
        FROM topo_files tf
        JOIN topo_imports ti ON tf.import_id = ti.id
        WHERE tf.import_id = :import_id 
        AND tf.stored_name = :filename
    """), {"import_id": import_id, "filename": filename}).first()
    
    if not file_record:
        raise HTTPException(404, "Fichier introuvable")
    
    # Vérifier permissions district
    if current_user["source"] == "geodoc":
        if current_user["role"] not in ["super_admin", "central_user"]:
            if file_record.target_district_id != current_user.get("id_district"):
                raise HTTPException(403, "Accès refusé à ce fichier")
    
    # Vérifier existence physique
    if not os.path.exists(file_record.storage_path):
        logger.error(f"Fichier physique introuvable: {file_record.storage_path}")
        raise HTTPException(404, "Fichier physique introuvable")
    
    # Retourner le fichier
    return FileResponse(
        path=file_record.storage_path,
        filename=filename,
        media_type=file_record.mime_type or "application/octet-stream"
    )
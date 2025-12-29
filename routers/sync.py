# routers/sync.py
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import json
import uuid
import logging

from database import get_db
from utils.security import verify_api_key_or_jwt
from utils.files import validate_file, save_file
import schemas

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=schemas.TopoSyncResponse, status_code=201)
async def sync_topo_data(
    data: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    current_user: dict = Depends(verify_api_key_or_jwt),
    db: Session = Depends(get_db)
):
    """Synchronisation TopoManager → GeODOC"""
    
    try:
        sync_data = json.loads(data)
        sync_request = schemas.TopoSyncRequest(**sync_data)
    except Exception as e:
        raise HTTPException(422, f"Erreur validation données: {str(e)}")
    
    # Vérifier dossier
    dossier = db.execute(text("""
        SELECT id, id_district, date_fermeture
        FROM dossiers
        WHERE id = :id
    """), {"id": sync_request.target_dossier_id}).first()
    
    if not dossier:
        raise HTTPException(404, f"Dossier {sync_request.target_dossier_id} introuvable")
    
    if dossier.date_fermeture:
        raise HTTPException(400, "Impossible d'importer dans un dossier fermé")
    
    target_district_id = dossier.id_district
    
    # Validation et matching
    warnings = []
    matched_entity_id = None
    match_confidence = None
    match_method = None
    matched_entity_details = None
    
    if sync_request.entity_type == schemas.EntityType.PROPRIETE:
        if not sync_request.entity_data.get("lot"):
            raise HTTPException(422, "Le champ 'lot' est obligatoire")
        if not sync_request.entity_data.get("nature"):
            raise HTTPException(422, "Le champ 'nature' est obligatoire")
        if not sync_request.entity_data.get("type_operation"):
            raise HTTPException(422, "Le champ 'type_operation' est obligatoire")
        if not sync_request.entity_data.get("vocation"):
            warnings.append("Vocation manquante (recommandée)")
        
        # Matching par lot
        lot = sync_request.entity_data.get("lot", "").strip()
        if lot:
            match = db.execute(text("""
                SELECT 
                    p.id, p.lot, p.titre, p.proprietaire, p.contenance,
                    p.nature, p.vocation, p.type_operation
                FROM proprietes p
                WHERE p.id_dossier = :dossier_id 
                AND UPPER(TRIM(p.lot)) = :lot
                LIMIT 1
            """), {
                "dossier_id": sync_request.target_dossier_id, 
                "lot": lot.upper()
            }).first()
            
            if match:
                matched_entity_id = match.id
                match_confidence = 1.0
                match_method = "exact_lot"
                matched_entity_details = {
                    "id": match.id,
                    "lot": match.lot,
                    "titre": match.titre,
                    "proprietaire": match.proprietaire,
                    "contenance": match.contenance,
                    "nature": match.nature,
                    "vocation": match.vocation,
                    "type_operation": match.type_operation
                }
                warnings.append(f"Propriété existante détectée (Lot {match.lot})")
    
    elif sync_request.entity_type == schemas.EntityType.DEMANDEUR:
        if not sync_request.entity_data.get("cin"):
            raise HTTPException(422, "Le champ 'cin' est obligatoire")
        if not sync_request.entity_data.get("nom_demandeur"):
            raise HTTPException(422, "Le champ 'nom_demandeur' est obligatoire")
        if not sync_request.entity_data.get("date_naissance"):
            raise HTTPException(422, "Le champ 'date_naissance' est obligatoire")
        if not sync_request.entity_data.get("titre_demandeur"):
            raise HTTPException(422, "Le champ 'titre_demandeur' est obligatoire")
        
        # Matching par CIN
        cin = sync_request.entity_data.get("cin", "").strip()
        if cin and len(cin) == 12:
            match = db.execute(text("""
                SELECT 
                    d.id, d.cin, d.nom_demandeur, d.prenom_demandeur,
                    d.date_naissance, d.titre_demandeur, d.domiciliation,
                    d.telephone
                FROM demandeurs d
                WHERE d.cin = :cin
                LIMIT 1
            """), {"cin": cin}).first()
            
            if match:
                matched_entity_id = match.id
                match_confidence = 1.0
                match_method = "exact_cin"
                matched_entity_details = {
                    "id": match.id,
                    "cin": match.cin,
                    "nom_demandeur": match.nom_demandeur,
                    "prenom_demandeur": match.prenom_demandeur,
                    "date_naissance": match.date_naissance.isoformat() if match.date_naissance else None,
                    "titre_demandeur": match.titre_demandeur,
                    "domiciliation": match.domiciliation,
                    "telephone": match.telephone
                }
                warnings.append(f"Demandeur existant détecté (CIN: {cin})")
    
    if matched_entity_id and sync_request.action_suggested == schemas.ActionSuggested.CREATE:
        sync_request.action_suggested = schemas.ActionSuggested.UPDATE
    
    # Créer import
    batch_id = str(uuid.uuid4())
    
    import_result = db.execute(text("""
        INSERT INTO topo_imports (
            batch_id, import_date, topo_user_id, topo_user_name,
            entity_type, action_suggested, target_dossier_id, target_district_id,
            raw_data, has_warnings, warnings,
            matched_entity_id, match_confidence, match_method, status
        ) VALUES (
            :batch_id, NOW(), :user_id, :user_name,
            :entity_type, :action, :dossier_id, :district_id,
            :raw_data, :has_warnings, :warnings,
            :matched_id, :confidence, :method, 'pending'
        ) RETURNING id, import_date
    """), {
        "batch_id": batch_id,
        "user_id": current_user["id"],
        "user_name": current_user.get("full_name") or current_user.get("username") or current_user.get("name"),
        "entity_type": sync_request.entity_type.value,
        "action": sync_request.action_suggested.value,
        "dossier_id": sync_request.target_dossier_id,
        "district_id": target_district_id,
        "raw_data": json.dumps(sync_request.entity_data, default=str),
        "has_warnings": len(warnings) > 0,
        "warnings": json.dumps(warnings) if warnings else None,
        "matched_id": matched_entity_id,
        "confidence": match_confidence,
        "method": match_method
    })
    
    import_record = import_result.first()
    import_id = import_record.id
    import_date = import_record.import_date
    
    # Upload fichiers
    uploaded_files = []
    if files:
        for file in files:
            validation = validate_file(file)
            if not validation["is_valid"]:
                warnings.extend([f"{file.filename}: {err}" for err in validation["errors"]])
                continue
            
            try:
                file_info = await save_file(file, "document", import_id)
                
                file_result = db.execute(text("""
                    INSERT INTO topo_files (
                        import_id, original_name, stored_name, storage_path,
                        mime_type, file_size, file_extension, category, file_hash, uploaded_at
                    ) VALUES (
                        :import_id, :original, :stored, :path,
                        :mime, :size, :ext, :category, :hash, NOW()
                    ) RETURNING id
                """), {
                    "import_id": import_id,
                    "original": file.filename,
                    "stored": file_info["stored_name"],
                    "path": file_info["storage_path"],
                    "mime": validation["file_info"]["mime_type"],
                    "size": file_info["file_size"],
                    "ext": validation["file_info"]["extension"],
                    "category": "document",
                    "hash": file_info["file_hash"]
                })
                
                file_id = file_result.first().id
                
                uploaded_files.append(schemas.FileResponse(
                    id=file_id,
                    original_name=file.filename,
                    stored_name=file_info["stored_name"],
                    file_size=file_info["file_size"],
                    category="document",
                    file_extension=validation["file_info"]["extension"],
                    mime_type=validation["file_info"]["mime_type"]
                ))
            except Exception as e:
                warnings.append(f"{file.filename}: {str(e)}")
    
    db.commit()
    
    match_details = None
    if matched_entity_id:
        match_details = schemas.MatchDetails(
            matched_entity_type=sync_request.entity_type.value,
            matched_entity_id=matched_entity_id,
            match_confidence=match_confidence,
            match_method=match_method,
            matched_entity_details=matched_entity_details
        )
    
    return schemas.TopoSyncResponse(
        success=True,
        message="Import créé avec succès",
        import_id=import_id,
        batch_id=batch_id,
        entity_type=sync_request.entity_type.value,
        action_suggested=sync_request.action_suggested.value,
        target_dossier_id=sync_request.target_dossier_id,
        target_district_id=target_district_id,
        has_warnings=len(warnings) > 0,
        warnings=warnings if warnings else None,
        match_found=matched_entity_id is not None,
        match_details=match_details,
        files_count=len(uploaded_files),
        files=uploaded_files,
        import_date=import_date
    )
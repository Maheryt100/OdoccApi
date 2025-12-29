# schemas.py - Schémas Pydantic alignés avec GeODOC
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum

# ========== ENUMS ==========
class EntityType(str, Enum):
    PROPRIETE = "propriete"
    DEMANDEUR = "demandeur"

class ActionSuggested(str, Enum):
    CREATE = "create"
    UPDATE = "update"

class Nature(str, Enum):
    URBAINE = "Urbaine"
    SUBURBAINE = "Suburbaine"
    RURALE = "Rurale"

class Vocation(str, Enum):
    EDILITAIRE = "Edilitaire"
    AGRICOLE = "Agricole"
    FORESTIERE = "Forestière"
    TOURISTIQUE = "Touristique"

class TypeOperation(str, Enum):
    MORCELLEMENT = "morcellement"
    IMMATRICULATION = "immatriculation"

# ========== AUTH ==========
class TopoUserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: dict

# ========== PROPRIETE (aligné avec migration GeODOC) ==========
class ProprieteData(BaseModel):
    # Champs obligatoires
    lot: str = Field(..., min_length=1, max_length=15)
    type_operation: TypeOperation
    nature: Nature
    
    # Champs optionnels (selon migration GeODOC)
    vocation: Optional[Vocation] = None
    proprietaire: Optional[str] = Field(None, max_length=100)
    titre: Optional[str] = Field(None, max_length=50)
    titre_mere: Optional[str] = Field(None, max_length=50)
    propriete_mere: Optional[str] = Field(None, max_length=50)
    contenance: Optional[int] = Field(None, gt=0)
    situation: Optional[str] = None
    charge: Optional[str] = Field(None, max_length=255)
    numero_FN: Optional[str] = Field(None, max_length=30)
    numero_requisition: Optional[str] = Field(None, max_length=50)
    
    # Dates (format ISO YYYY-MM-DD)
    date_requisition: Optional[date] = None
    date_depot_1: Optional[date] = None
    date_depot_2: Optional[date] = None
    date_approbation_acte: Optional[date] = None
    
    # Dépôt/Volume Inscription
    dep_vol_inscription: Optional[str] = Field(None, max_length=50)
    numero_dep_vol_inscription: Optional[str] = Field(None, max_length=50)
    
    # Dépôt/Volume Réquisition
    dep_vol_requisition: Optional[str] = Field(None, max_length=50)
    numero_dep_vol_requisition: Optional[str] = Field(None, max_length=50)
    
    @field_validator('date_approbation_acte')
    def validate_approbation(cls, v, info):
        if v and info.data.get('date_requisition'):
            if v < info.data['date_requisition']:
                raise ValueError('date_approbation_acte ne peut pas être avant date_requisition')
        return v

# ========== DEMANDEUR (aligné avec migration GeODOC) ==========
class DemandeurData(BaseModel):
    # Champs obligatoires
    titre_demandeur: str = Field(..., max_length=20)
    nom_demandeur: str = Field(..., min_length=1, max_length=100)
    date_naissance: date
    cin: str = Field(..., min_length=12, max_length=12, pattern=r'^\d{12}$')
    
    # Champs optionnels (selon migration)
    prenom_demandeur: Optional[str] = Field(None, max_length=100)
    lieu_naissance: Optional[str] = Field(None, max_length=100)
    sexe: Optional[str] = Field(None, max_length=10)
    occupation: Optional[str] = Field(None, max_length=100)
    nom_pere: Optional[str] = None
    nom_mere: Optional[str] = None
    
    # Dates CIN
    date_delivrance: Optional[date] = None
    lieu_delivrance: Optional[str] = Field(None, max_length=100)
    date_delivrance_duplicata: Optional[date] = None
    lieu_delivrance_duplicata: Optional[str] = Field(None, max_length=100)
    
    # Contact
    domiciliation: Optional[str] = Field(None, max_length=150)
    telephone: Optional[str] = Field(None, max_length=15, pattern=r'^\d{10}$')
    nationalite: Optional[str] = Field(default='Malagasy', max_length=50)
    
    # Situation familiale
    situation_familiale: Optional[str] = Field(None, max_length=50)
    regime_matrimoniale: Optional[str] = Field(None, max_length=50)
    date_mariage: Optional[date] = None
    lieu_mariage: Optional[str] = Field(None, max_length=100)
    marie_a: Optional[str] = None
    
    @field_validator('sexe')
    def validate_sexe(cls, v, info):
        titre = info.data.get('titre_demandeur')
        if titre == 'Monsieur' and v and v != 'Homme':
            return 'Homme'
        elif titre in ['Madame', 'Mademoiselle'] and v and v != 'Femme':
            return 'Femme'
        return v

# ========== SYNC REQUEST ==========
class TopoSyncRequest(BaseModel):
    entity_type: EntityType
    action_suggested: ActionSuggested
    target_dossier_id: int = Field(..., gt=0)
    entity_data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

# ========== RESPONSES ==========
class FileResponse(BaseModel):
    id: int
    original_name: str
    stored_name: str
    file_size: int
    category: str
    file_extension: str
    mime_type: str

class MatchDetails(BaseModel):
    matched_entity_type: str
    matched_entity_id: int
    match_confidence: float
    match_method: str
    matched_entity_details: Optional[Dict[str, Any]] = None

class TopoSyncResponse(BaseModel):
    success: bool
    message: str
    import_id: int
    batch_id: str
    entity_type: str
    action_suggested: str
    target_dossier_id: int
    target_district_id: int
    has_warnings: bool
    warnings: Optional[List[str]] = None
    match_found: bool
    match_details: Optional[MatchDetails] = None
    files_count: int
    files: List[FileResponse] = []
    import_date: datetime

class DossierSearchResult(BaseModel):
    id: int
    nom_dossier: str
    numero_ouverture: int
    commune: str
    fokontany: str
    district_id: int
    district_nom: str
    is_closed: bool
    proprietes_count: int = 0
    demandeurs_count: int = 0

# ========== STAGING ==========
class StagingItemResponse(BaseModel):
    id: int
    batch_id: str
    entity_type: str
    action_suggested: str
    dossier_id: int
    dossier_nom: str
    dossier_numero_ouverture: int
    district_id: int
    district_nom: str
    raw_data: dict
    matched_entity_id: Optional[int] = None
    matched_entity_details: Optional[dict] = None
    match_confidence: Optional[float] = None
    match_method: Optional[str] = None
    has_warnings: bool
    warnings: Optional[List[str]] = None
    files_count: int
    files: List[dict] = []
    topo_user_name: str
    import_date: datetime
    status: str
    processed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

class ValidateImportRequest(BaseModel):
    action: str = Field(..., pattern=r'^(accept|reject)$')
    rejection_reason: Optional[str] = Field(None, min_length=10)
    
    @field_validator('rejection_reason')
    def validate_rejection_reason(cls, v, info):
        if info.data.get('action') == 'reject' and not v:
            raise ValueError('rejection_reason requis pour action=reject')
        return v

# ========== STATS ==========
class StatsResponse(BaseModel):
    total: int = 0
    pending: int = 0
    validated: int = 0
    rejected: int = 0
    with_warnings: int = 0
    by_entity_type: Dict[str, int] = {}
    by_district: Dict[str, int] = {}
    recent_imports: List[Dict[str, Any]] = []
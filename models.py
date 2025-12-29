# models.py
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean, Text, DateTime, BigInteger, Enum
from datetime import datetime
from database import Base
import enum

class TopoUser(Base):
    """Utilisateurs TopoManager"""
    __tablename__ = "topo_users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True)
    full_name = Column(String(100))
    password_hash = Column(String(255))
    role = Column(String(20), default='operator')
    is_active = Column(Boolean, default=True)
    allowed_districts = Column(Text)  # JSON sous forme de texte
    last_token_refresh = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Dossier(Base):
    """Dossiers GeODOC"""
    __tablename__ = "dossiers"
    
    id = Column(Integer, primary_key=True, index=True)
    nom_dossier = Column(String(100), index=True)
    numero_ouverture = Column(Integer, unique=True, index=True)
    date_descente_debut = Column(Date)
    date_descente_fin = Column(Date)
    type_commune = Column(String(50))
    commune = Column(String(100), index=True)
    fokontany = Column(String(100))
    circonscription = Column(String(100))
    id_district = Column(Integer, ForeignKey("districts.id"), index=True)
    id_user = Column(Integer, ForeignKey("users.id"))
    date_fermeture = Column(Date, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Propriete(Base):
    """Propriétés"""
    __tablename__ = "proprietes"
    
    id = Column(Integer, primary_key=True, index=True)
    lot = Column(String(15), index=True)
    titre = Column(String(50), index=True)
    proprietaire = Column(String(100))
    contenance = Column(BigInteger)
    nature = Column(String(50))
    vocation = Column(String(50))
    type_operation = Column(String(50))
    situation = Column(Text)
    id_dossier = Column(Integer, ForeignKey("dossiers.id"), index=True)
    id_user = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class Demandeur(Base):
    """Demandeurs"""
    __tablename__ = "demandeurs"
    
    id = Column(Integer, primary_key=True, index=True)
    titre_demandeur = Column(String(20))
    nom_demandeur = Column(String(100), index=True)
    prenom_demandeur = Column(String(100))
    date_naissance = Column(Date)
    cin = Column(String(15), unique=True, index=True)
    domiciliation = Column(String(150))
    telephone = Column(String(15))
    id_user = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class ImportStatus(str, enum.Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ERROR = "error"

class TopoImport(Base):
    """Imports TopoManager en attente"""
    __tablename__ = "topo_imports"
    
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(36), index=True)
    import_date = Column(DateTime, default=datetime.utcnow)
    topo_user_id = Column(Integer, index=True)
    topo_user_name = Column(String(100))
    entity_type = Column(String(20))
    action_suggested = Column(String(20))
    target_dossier_id = Column(Integer, ForeignKey("dossiers.id"), index=True)
    target_district_id = Column(Integer, ForeignKey("districts.id"), index=True)
    raw_data = Column(Text)  # JSON
    has_warnings = Column(Boolean, default=False)
    warnings = Column(Text)  # JSON
    matched_entity_id = Column(Integer)
    match_confidence = Column(Integer)
    match_method = Column(String(50))
    status = Column(String(20), default='pending', index=True)
    processed_at = Column(DateTime)
    processed_by = Column(Integer, ForeignKey("users.id"))
    rejection_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class TopoFile(Base):
    """Fichiers liés aux imports"""
    __tablename__ = "topo_files"
    
    id = Column(Integer, primary_key=True, index=True)
    import_id = Column(Integer, ForeignKey("topo_imports.id"), index=True)
    original_name = Column(String(255))
    stored_name = Column(String(255), unique=True)
    storage_path = Column(String(500))
    mime_type = Column(String(100))
    file_size = Column(BigInteger)
    file_extension = Column(String(10))
    category = Column(String(20))
    description = Column(Text)
    file_hash = Column(String(64))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class District(Base):
    """Districts"""
    __tablename__ = "districts"
    
    id = Column(Integer, primary_key=True, index=True)
    nom_district = Column(String(100), index=True)
    id_region = Column(Integer)

class User(Base):
    """Utilisateurs GeODOC"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    password = Column(String(255))
    role = Column(String(50), default='user')
    id_district = Column(Integer, ForeignKey("districts.id"))
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
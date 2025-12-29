# main.py - Point d'entrée FastAPI (CORRIGÉ)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
import os
import atexit
import logging

from database import check_database_connection
from routers import auth, dossiers, sync, staging
from utils.cleanup import cleanup_old_imports

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/topo_staging")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")

# Créer le répertoire d'upload
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================
# INITIALISATION FASTAPI (UNE SEULE FOIS)
# ============================================

app = FastAPI(
    title="GeODOC API - Interopérabilité TopoManager",
    description="API de synchronisation TopoManager ↔ GeODOC",
    version="1.0.0",
    swagger_ui_parameters={
        "persistAuthorization": True
    }
)

# ============================================
# MIDDLEWARES
# ============================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# MONTER LES FICHIERS STATIQUES
# ============================================

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ============================================
# ENREGISTRER LES ROUTERS
# ============================================

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(dossiers.router, prefix="/api/v1/dossiers", tags=["Dossiers"])
app.include_router(sync.router, prefix="/api/v1/topo-sync", tags=["Synchronisation"])
app.include_router(staging.router, prefix="/api/v1/staging", tags=["Staging"])

# ============================================
# ROUTES RACINE
# ============================================

@app.get("/")
def root():
    return {
        "message": "API GeODOC - Interopérabilité TopoManager",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "auth": "/api/v1/auth",
            "sync": "/api/v1/topo-sync",
            "staging": "/api/v1/staging",
            "dossiers": "/api/v1/dossiers"
        }
    }

@app.get("/health")
def health_check():
    db_status = "connected" if check_database_connection() else "disconnected"
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status
    }

# ============================================
# TÂCHES PLANIFIÉES
# ============================================

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_old_imports, 'cron', hour=2)  # Tous les jours à 2h du matin
scheduler.start()

# Arrêter le scheduler lors de l'arrêt de l'app
atexit.register(lambda: scheduler.shutdown())

logger.info("✅ API FastAPI GeODOC démarrée avec succès")
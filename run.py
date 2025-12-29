#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de lancement de l'API FastAPI GeODOC
Usage: python run.py [--reload] [--port PORT]
"""

import sys
import argparse
import uvicorn
import os
from dotenv import load_dotenv

# Forcer l'encodage UTF-8 sur Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description='Lancer l\'API FastAPI GeODOC')
    parser.add_argument(
        '--reload', 
        action='store_true',
        help='Activer le rechargement automatique (dev)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('API_PORT', 8000)),
        help='Port à utiliser'
    )
    parser.add_argument(
        '--host',
        type=str,
        default=os.getenv('API_HOST', '0.0.0.0'),
        help='Hôte à écouter'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🚀 Démarrage de l'API FastAPI GeODOC")
    print("="*60)
    print(f"📍 URL: http://{args.host}:{args.port}")
    print(f"📚 Documentation: http://{args.host}:{args.port}/docs")
    print(f"🔧 Mode: {'DÉVELOPPEMENT' if args.reload else 'PRODUCTION'}")
    print("="*60 + "\n")
    
    # Lancer le serveur
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Arrêt de l'API...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1)
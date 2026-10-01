#!/usr/bin/env bash
# Copia de seguridad de la base de datos (facturas, gastos, CRM, logo) a ./backups
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
out="backups/gestion-$(date +%Y%m%d-%H%M%S).db"
docker compose exec -T app python -c "
import sqlite3
src = sqlite3.connect('/data/gestion.db'); dst = sqlite3.connect('/tmp/backup.db'); src.backup(dst); dst.close()"
docker compose cp app:/tmp/backup.db "$out"
echo "Copia guardada en $out"

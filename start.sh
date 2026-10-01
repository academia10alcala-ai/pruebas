#!/usr/bin/env bash
# Arranca la aplicación con Docker. Uso: ./start.sh [https]
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se ha creado .env. Edítalo y cambia APP_PASSWORD antes de continuar."
  exit 1
fi
if grep -q '^APP_PASSWORD=cambia-esta' .env; then
  echo "Cambia APP_PASSWORD en .env (sigue con el valor de ejemplo)."
  exit 1
fi

if [ "${1:-}" = "https" ]; then
  docker compose --profile https up -d --build
  echo "Listo: https://$(grep '^DOMAIN=' .env | cut -d= -f2)"
else
  docker compose up -d --build
  echo "Listo: http://localhost:$(grep '^PORT=' .env | cut -d= -f2 || echo 8000)"
fi

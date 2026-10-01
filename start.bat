@echo off
rem Arranca la aplicacion con Docker Desktop (Windows).
cd /d "%~dp0"
if not exist .env (
  copy .env.example .env >nul
  echo Se ha creado .env. Editalo y cambia APP_PASSWORD, luego vuelve a ejecutar este fichero.
  pause & exit /b 1
)
docker compose up -d --build
echo Listo: http://localhost:8000
pause

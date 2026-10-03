@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Programa de gestion

rem --- 1. Buscar Python ---
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (
  python --version >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo  No se encuentra Python en este ordenador.
  echo  Se va a abrir la pagina de descarga. Instala Python 3.12 y
  echo  MARCA la casilla "Add python.exe to PATH" en la primera pantalla.
  echo  Despues vuelve a hacer doble clic en este archivo.
  echo.
  start https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

rem --- 2. Preparar el programa (solo la primera vez, necesita internet) ---
if not exist ".venv\Scripts\python.exe" (
  echo Preparando el programa por primera vez. Puede tardar un par de minutos...
  %PY% -m venv .venv || goto :error
)
if not exist ".venv\instalado.txt" (
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt || goto :error
  echo ok> ".venv\instalado.txt"
)

rem --- 3. Arrancar ---
".venv\Scripts\python.exe" launcher.py
pause
exit /b 0

:error
echo.
echo  Algo ha fallado en la preparacion. Haz una foto o copia el texto de arriba y envialo.
pause
exit /b 1

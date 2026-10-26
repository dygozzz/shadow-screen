@echo off
rem One-click diagnostics: prepares an isolated Python environment, then runs tools\diag.py,
rem which writes a zip with a full log to the Desktop.
setlocal
title Shadow Screen - diagnostico
cd /d "%~dp0"

set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "VENV=%LOCALAPPDATA%\ShadowScreenDiag\venv"
set "PIPLOG=%TEMP%\shadowscreen-pip.log"

echo ======================================================================
echo  Shadow Screen - diagnostico
echo  Deixe o teclado ligado POR CABO USB antes de continuar.
echo ======================================================================
echo.

if not exist "%PY312%" (
  echo [1/3] Python 3.12 nao encontrado. Instalando pelo winget...
  winget install --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
)
if not exist "%PY312%" (
  echo.
  echo Nao consegui instalar o Python 3.12 automaticamente.
  echo Instale por https://www.python.org/downloads/release/python-31210/ e rode este arquivo de novo.
  pause
  exit /b 1
)
echo [1/3] Python 3.12 OK

if not exist "%VENV%\Scripts\python.exe" (
  echo [2/3] Criando ambiente isolado em %VENV% ...
  "%PY312%" -m venv "%VENV%"
)
if not exist "%VENV%\Scripts\python.exe" (
  echo Falha ao criar o ambiente isolado.
  pause
  exit /b 1
)
echo [2/3] Ambiente OK

echo [3/3] Instalando/atualizando pacotes (hidapi, frida, pillow)... pode demorar um pouco
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade hidapi frida pillow > "%PIPLOG%" 2>&1
echo.

"%VENV%\Scripts\python.exe" tools\diag.py --pip-log "%PIPLOG%"
echo.
pause

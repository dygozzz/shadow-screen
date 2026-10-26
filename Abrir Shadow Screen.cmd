@echo off
rem Serves Shadow Screen on localhost (WebHID needs a secure context) and opens it in the browser.
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
start "Shadow Screen (pode minimizar)" /min "%PY%" -m http.server 8765 --bind 127.0.0.1 -d "%~dp0."
timeout /t 1 /nobreak >nul
start "" http://localhost:8765/

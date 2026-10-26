@echo off
rem Creates "Shadow Screen" shortcuts (Start Menu + Desktop) that run the launcher with pythonw,
rem so no console shows up and no unsigned .exe is needed (works with Smart App Control on).
setlocal
set "ROOT=%~dp0"
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" (
  echo Python 3.12 nao encontrado em "%PYW%". Instale com: winget install Python.Python.3.12
  pause
  exit /b 1
)
echo Instalando dependencias (hidapi, pywebview)...
"%PYW:pythonw.exe=python.exe%" -m pip install --user --quiet --disable-pip-version-check hidapi pywebview || (
  echo Falha ao instalar as dependencias.
  pause
  exit /b 1
)
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "foreach ($dir in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {" ^
  "  $lnk = $ws.CreateShortcut((Join-Path $dir 'Shadow Screen.lnk'));" ^
  "  $lnk.TargetPath = '%PYW%';" ^
  "  $lnk.Arguments = '\"%ROOT%launcher\shadow_screen.py\"';" ^
  "  $lnk.WorkingDirectory = '%ROOT%';" ^
  "  $lnk.IconLocation = '%ROOT%launcher\icon.ico';" ^
  "  $lnk.Description = 'Envia GIFs para a tela do EPOMAKER Shadow-S';" ^
  "  $lnk.Save() }"
echo Atalhos criados no Menu Iniciar e na Area de Trabalho.

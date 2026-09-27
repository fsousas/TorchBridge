@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  call INSTALAR.bat
  if errorlevel 1 exit /b 1
)
.venv\Scripts\python.exe scripts\build_fullscreen.py
if errorlevel 1 (
  echo Instale CMake e Visual Studio Build Tools com o componente C++ para x86.
  pause
  exit /b 1
)
echo Modulo pronto. Use o menu do icone TB para instalar no Torchlight.
pause

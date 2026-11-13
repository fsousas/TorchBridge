@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe scripts\build_native_input.py
if errorlevel 1 exit /b 1
echo Modulo gerado. Use "Instalar movimento seguro..." no menu do TorchBridge.

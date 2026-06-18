@echo off
cd /d "%~dp0"
echo Iniciando servidor Chatbot Tienda de Abastos...
echo.
set PYTHONIOENCODING=utf-8
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" run_app.py
) else if exist ".venv311\Scripts\python.exe" (
  ".venv311\Scripts\python.exe" run_app.py
) else (
  python run_app.py
)
pause

@echo off
REM ===== SEDUC Monitoramento Orcamentario - inicializacao =====
cd /d "%~dp0"
echo Verificando dependencias...
python -m pip install -r backend\requirements.txt
echo.
echo Iniciando servidor em http://127.0.0.1:8000 ...
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

@echo off
REM Testa a Critica do Cora por HTTP (sem navegador). Usa CORA_USER/CORA_PASS do .env.
cd /d "%~dp0cora-web-driver"
"%~dp0venv\Scripts\python.exe" cli.py executar --operacao critica --job-id teste-http
pause

@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
echo.
echo === Testes ===
python -m pytest tests/promax_http -q
echo.
echo === Grupo inadimplencia via HTTP, sem publicar ===
set PROMAX_HTTP_GRUPOS=inadimplencia
python cli.py relatorios --perfil inadimplencia --somente-baixar
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
pause

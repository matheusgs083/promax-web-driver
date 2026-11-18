@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo === Testes ===
python -m pytest tests/promax_http -q
echo.
echo === Grupo estoque inteiro via HTTP (sem Edge), sem publicar ===
set PROMAX_HTTP_GRUPOS=estoque
python cli.py relatorios --perfil estoque --somente-baixar
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
pause

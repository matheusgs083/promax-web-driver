@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
echo.
echo === 15.05.01 (OBZ) via HTTP, sem publicar ===
set PROMAX_HTTP_GRUPOS=obz
python cli.py relatorios --perfil obz --rotinas 150501 --somente-baixar
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
echo Arquivos em DOWNLOAD_DIR\150501 ; rastro em logs\promax_http
pause

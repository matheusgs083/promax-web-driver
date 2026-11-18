@setlocal EnableDelayedExpansion
@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo === Testes ===
python -m pytest tests/promax_http -q
set PROMAX_HTTP_GRUPOS=estoque,adf,nfs_incentivo,giro,outros
for %%G in (adf nfs_incentivo giro outros) do (
    echo.
    echo === Grupo %%G via HTTP, sem publicar ===
    python cli.py relatorios --perfil %%G --somente-baixar
    echo CODIGO_SAIDA %%G=!ERRORLEVEL!
)
echo.
echo Fim. Arquivos em DOWNLOAD_DIR; log em logs\app.log
pause

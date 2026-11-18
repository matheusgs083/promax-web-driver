@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
echo.
echo === Testes ===
python -m pytest tests/promax_http -q
echo.
echo === 03114902 Geo Bot (tela PH) via HTTP, sem publicar ===
set PROMAX_HTTP_GRUPOS=bot_zap
python cli.py relatorios --perfil bot_zap --rotinas 03114902_BOT --somente-baixar
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
pause

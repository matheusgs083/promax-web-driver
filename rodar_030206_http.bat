@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
echo.
echo === Testes ===
python -m pytest tests/promax_http -q
echo.
echo === 030206 Bot (PDF de boletos) via HTTP, Sousa e Patos, sem publicar ===
set PROMAX_HTTP_GRUPOS=bot_zap
python cli.py relatorios --perfil bot_zap --rotinas 030206_BOT --unidade 0640001 --unidade 2210003 --somente-baixar
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
pause

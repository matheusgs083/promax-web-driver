@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
echo A 030206 (PDF de boletos) continua no Edge e fica fora deste teste.
echo.
echo === Testes ===
python -m pytest tests/promax_http -q
echo.
echo === bot_zap via HTTP (so Patos), sem publicar ===
set PROMAX_HTTP_GRUPOS=bot_zap
python cli.py relatorios --perfil bot_zap --rotinas 120601_BOT 020220_BOT 030111_BOT 031702_BOT 020304_BOT 031120_BOT --unidade 2210003 --somente-baixar
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
pause

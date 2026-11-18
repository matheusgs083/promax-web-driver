@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
echo.
echo === botzapfechamento via HTTP: 0513, 120601 e 020220 do mes passado (so Patos), sem publicar ===
set PROMAX_HTTP_GRUPOS=botzapfechamento
python cli.py fechamento --perfil botzapfechamento --rotinas 0513 120601 020220 --unidade 2210003 --somente-baixar
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
pause

@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
set PROMAX_REPORT_UNIT=PATOS
echo.
echo === Testes ===
python -m pytest tests/promax_http -q
echo.
echo === Liga Entrega: 030805 e 1706 via HTTP (Patos e Sume), sem publicar ===
set PROMAX_HTTP_GRUPOS=liga_entrega
python cli.py relatorios --perfil liga_entrega --rotinas 030805_LIGA 1706_BI_INDICADORES --unidade 2210003 --unidade 2210004 --somente-baixar
echo CODIGO_SAIDA=%ERRORLEVEL%
pause

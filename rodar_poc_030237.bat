@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo === Testes offline ===
python -m pytest tests/promax_http -q
echo.
echo === PoC 030237 Patos (download sem Edge) ===
python -m promax_http.poc --rotina 030237 --unidade 2210003 --campo quebra1=14 --campo quebra2=12 --campo quebra3=16 --campo quebra1Inicial=0 --campo quebra1Final=99999999 --campo quebra2Inicial=0 --campo quebra2Final=99999999 --campo quebra3Inicial=0 --campo quebra3Final=99999999 --campo dataInicial=01/11/2026 --campo dataFinal=16/11/2026
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
echo Log completo em logs\app.log
pause

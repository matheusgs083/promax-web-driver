@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Captura das telas de todas as rotinas de relatorio (nao gera relatorio).
echo Para capturar so algumas: capturar_telas_relatorios.bat 140501 020502
echo.
python -m promax_http.capturar_telas %*
echo.
echo Resultado em data\promax_telas\resumo.txt
pause

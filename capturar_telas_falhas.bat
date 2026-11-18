@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Recaptura das 5 rotinas que falharam: 0105070402 03114902 120606 120616 140510
echo.
python -m promax_http.capturar_telas 0105070402 03114902 120606 120616 140510
echo.
echo Resultado em data\promax_telas\resumo.txt
pause

@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: usa o mesmo usuario Promax. Pare o mainWorker se ele estiver rodando neste PC.
echo.
python -m promax_http.capturar_ph
echo.
echo Pronto. Avise o Claude: ele le os arquivos direto da pasta do projeto.
pause

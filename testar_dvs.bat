@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
echo Teste da 030805 e da 1706 por HTTP: gera em Patos e Sume e procura o arquivo no DVS
echo (pasta de rede e URLs /arquivos/). Os arquivos achados vao para data\promax_telas\_dvs_teste
echo.
set PROMAX_REPORT_UNIT=PATOS
python -m promax_http.testar_dvs
echo.
echo CODIGO_SAIDA=%ERRORLEVEL%
pause

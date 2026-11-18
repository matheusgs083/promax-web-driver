@echo off
REM Limpa a gravacao de rede do Cora (senha, tokens e cookies) antes de compartilhar.
cd /d "%~dp0"
set ENTRADA=%USERPROFILE%\Downloads\cora.har
set SAIDA=%~dp0..\logs\cora_limpo.har
if not exist "%ENTRADA%" (
  echo Nao achei %ENTRADA%. Salve a gravacao do F12 com esse nome na pasta Downloads.
  pause
  exit /b 1
)
"%~dp0..\venv\Scripts\python.exe" limpar_har.py "%ENTRADA%" "%SAIDA%"
if errorlevel 1 ( pause & exit /b 1 )
del "%ENTRADA%"
echo Gravacao original apagada. Arquivo limpo em %SAIDA%
pause

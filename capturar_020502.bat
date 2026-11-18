@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python -m promax_http.poc --rotina 020502 --unidade 2210003 --so-abrir
echo.
echo Pronto. Pode fechar esta janela.
pause

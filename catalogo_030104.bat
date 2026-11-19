@echo off
REM Le as condicoes de pagamento liberadas na 030104 (Patos). Nao digita nada.
REM Saida: JSON na tela e em logs\promax_http\<data>_pedido_030104\resultado.json. Pare o mainWorker antes.
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m promax_http.pedido_030104 --catalogo %*
pause

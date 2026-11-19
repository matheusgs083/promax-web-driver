@echo off
REM Explora a 030104 passo a passo SEM gravar pedido (nao adiciona item nem salva).
REM Usa o 1o pedido da planilha de pedidos do .env. Pare o mainWorker antes.
REM Para escolher os dados: explorar_030104.bat --mapa 123 --vendedor 45 --operacao 1 --cliente 9999 --produto 1234 --qtd 5
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m promax_http.explorar_030104 %*
pause

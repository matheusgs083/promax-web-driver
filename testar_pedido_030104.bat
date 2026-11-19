@echo off
REM TESTE REAL: digita e SALVA 1 pedido na 030104 em Patos (mapa gerado pelo Promax).
REM Setor 992, operacao 1, cliente 16883, produto 2349, quantidade 2, preco 44,00. Pare o mainWorker antes.
REM Para antes de salvar se o Promax mostrar alerta, pergunta ou faltar campo.
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m promax_http.pedido_030104 --mapa 0 --vendedor 992 --operacao 1 --cliente 16883 --produto 2349 --qtd 2 --ttv 44,00 --salvar %*
pause

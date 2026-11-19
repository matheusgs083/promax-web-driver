@echo off
REM Captura a tela da 030104 (Digitacao de Pedidos) em Patos. So abre e salva a tela; nao digita nem grava pedido.
REM Pare o mainWorker antes: o Promax aceita uma sessao por usuario.
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m promax_http.capturar_telas 030104 --unidade 2210003
pause
